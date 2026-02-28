from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
import json
import math
from pathlib import Path

app = FastAPI(
    title="NJ Restaurant Market Gap API",
    description="Helps entrepreneurs find underserved restaurant opportunities in New Jersey.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Load gap analysis data at startup ─────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "gap_analysis.json") as f:
    GAP_DATA: list[dict] = json.load(f)

with open(DATA_DIR / "yelp_nj_restaurants.json") as f:
    RESTAURANTS: list[dict] = json.load(f)

# Index for fast lookup
GAP_BY_ZIP = {z["zip"]: z for z in GAP_DATA}
RESTAURANTS_BY_ZIP: dict[str, list] = {}
for r in RESTAURANTS:
    z = r.get("postal_code", "")
    RESTAURANTS_BY_ZIP.setdefault(z, []).append(r)

ALL_CUISINES = sorted({
    g["cuisine"]
    for z in GAP_DATA
    for g in z["top_cuisine_gaps"]
})

ALL_ATTRIBUTES = ["BYOB", "Delivery", "Outdoor Seating", "Kid-Friendly", "Late Night", "Free WiFi", "Reservations"]


# ── Load survival model at startup ────────────────────────────────────────────
MODEL_DIR = Path(__file__).parent.parent / "models"
_survival_model = None
_model_metadata = None
_feature_importance = None
_shap_explainer = None  # per-request SHAP explanations

def _load_survival_model():
    """Lazy-load the XGBoost survival model. Fails gracefully if not present."""
    global _survival_model, _model_metadata, _feature_importance, _shap_explainer

    meta_path = MODEL_DIR / "model_metadata.json"
    model_path = MODEL_DIR / "survival_model.json"
    imp_path   = MODEL_DIR / "feature_importance.json"

    if not meta_path.exists() or not model_path.exists():
        print("⚠  Survival model not found — /predict will return 503.")
        print("   Run: python backend/train_survival_model.py")
        return

    try:
        import xgboost as xgb
        with open(meta_path) as f:
            _model_metadata = json.load(f)
        with open(imp_path) as f:
            _feature_importance = json.load(f)

        _survival_model = xgb.XGBClassifier()
        _survival_model.load_model(str(model_path))
        print(f"✓ Survival model loaded  (AUC={_model_metadata['metrics']['cv_roc_auc_mean']})")

        # Build SHAP TreeExplainer once — cheap at load time, fast at inference
        try:
            import shap
            _shap_explainer = shap.TreeExplainer(_survival_model)
            print("✓ SHAP explainer ready")
        except ImportError:
            print("⚠  shap not installed — per-request explanations unavailable. pip install shap")
        except Exception as se:
            print(f"⚠  SHAP explainer failed: {se}")

        # Load global feature importance as fallback
        try:
            imp_path = Path("models/feature_importance.json")
            if imp_path.exists():
                with open(imp_path) as f:
                    global _global_importance
                    _global_importance = json.load(f)
                print("✓ Global importance fallback loaded")
        except:
            pass

    except ImportError:
        print("⚠  xgboost not installed — /predict unavailable. pip install xgboost")
    except Exception as e:
        print(f"⚠  Could not load survival model: {e}")

_load_survival_model()


# ── Scoring helpers ───────────────────────────────────────────────────────────

def opportunity_score(z: dict, cuisine_filter: str = None) -> float:
    if cuisine_filter:
        gaps = [g for g in z["top_cuisine_gaps"] if g["cuisine"] == cuisine_filter]
        top_gap = gaps[0]["gap_score"] if gaps else 0
    else:
        top_gap = z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0

    market_size = math.log(z["total_reviews"] + 1)
    # Cap attr_bonus at 10 so zips with many attribute mismatches don't
    # dominate zips with genuine cuisine opportunities.
    attr_bonus = min(len(z["attr_gaps"]) * 2.5, 10.0)
    return round(top_gap * 0.6 + market_size * 2 + attr_bonus, 2)


def risk_label(closure_rate: float) -> str:
    if closure_rate < 0.2:  return "low"
    if closure_rate < 0.35: return "medium"
    return "high"


def _get_jitter(zip_code: str, scale: float = 2.5) -> float:
    """Deterministic jitter based on zip code to keep rankings stable."""
    import hashlib
    h = hashlib.md5(zip_code.encode()).hexdigest()
    # Convert first 4 chars of md5 to a float between -scale and +scale
    val = int(h[:4], 16) / 65535.0
    return round((val - 0.5) * 2 * scale, 1)


def format_zip(z: dict, cuisine_filter: str = None) -> dict:
    score = opportunity_score(z, cuisine_filter)
    top_gaps = z["top_cuisine_gaps"]
    if cuisine_filter:
        matched = [g for g in top_gaps if g["cuisine"] == cuisine_filter]
        top_gaps = matched + [g for g in top_gaps if g["cuisine"] != cuisine_filter]

    return {
        "zip": z["zip"],
        "city": z["city"],
        "opportunity_score": score,
        "risk": risk_label(z["closure_rate"]),
        "closure_rate": z["closure_rate"],
        "avg_stars": z["avg_stars"],
        "total_reviews": z["total_reviews"],
        "total_restaurants": z["total_restaurants"],
        "open_restaurants": z["open_restaurants"],
        "avg_price_tier": z["avg_price"],
        "top_cuisine_gaps": top_gaps[:3],
        "attr_gaps": z["attr_gaps"],
    }


# ── Predict helpers ───────────────────────────────────────────────────────────

CUISINE_KEYWORDS = [
    "American", "Italian", "Chinese", "Japanese", "Mexican", "Thai",
    "Indian", "Korean", "Mediterranean", "Greek", "Vietnamese", "French",
    "Spanish", "Middle Eastern", "Pizza", "Burgers", "Seafood", "Sushi",
    "Barbecue", "Sandwiches", "Breakfast", "Desserts", "Vegan",
]

NOISE_MAP = {"quiet": 0, "average": 1, "loud": 2, "very_loud": 3}

# ── Cuisine Smart Defaults ──────────────────────────────────────────────────
CUISINE_DEFAULTS = {
    "American": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 1, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Japanese": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 1, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Sushi": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 1, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "quiet"},
    "Italian": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 1, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Chinese": {"price_tier": 1.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "quiet"},
    "Thai": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 1, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "quiet"},
    "Mexican": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Pizza": {"price_tier": 1.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Sandwiches": {"price_tier": 1.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 0, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Burgers": {"price_tier": 1.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0, "good_for_kids": 1, "has_reservations": 0, "has_wifi": 1, "has_alcohol": 0, "has_tv": 1, "good_for_groups": 1, "noise_level": "average"},
    "Vegan": {"price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 1, "good_for_kids": 1, "has_reservations": 1, "has_wifi": 1, "has_alcohol": 0, "has_tv": 0, "good_for_groups": 1, "noise_level": "average"},
}

GLOBAL_DEFAULTS = {
    "price_tier": 2.0, "has_delivery": 1, "has_takeout": 1, "has_outdoor_seating": 0,
    "good_for_kids": 1, "has_reservations": 0, "has_wifi": 0, "has_alcohol": 0,
    "has_tv": 1, "good_for_groups": 1, "noise_level": "average"
}

def _build_feature_vector(concept: dict, zip_context: dict) -> list[float]:
    """
    Build the feature vector expected by the survival model.
    concept: fields from the PredictRequest
    zip_context: the gap_analysis record for the target zip
    """
    feats = _model_metadata["feature_cols"]

    # Zip-level proxy for "market context" features
    # When predicting a new concept, we don't have review history yet.
    # We use zip averages as priors and concept attributes directly.
    zip_avg_stars  = zip_context.get("avg_stars", 3.5)
    zip_closure    = zip_context.get("closure_rate", 0.25)
    total_reviews  = zip_context.get("total_reviews", 1000)

    # Cuisine flags
    cuisine_flags = {}
    for ck in CUISINE_KEYWORDS:
        col = f"cuisine_{ck.lower().replace(' ', '_')}"
        cuisine_flags[col] = 1 if ck.lower() in concept.get("cuisine", "").lower() else 0

    # Base lookup — uses zip-market-level priors for review-history features.
    # NOTE: leakage features (lifespan_days, review velocities) are intentionally
    # excluded from training, so they won't appear in `feats` at all.
    lookup = {
        # Yelp base (hypothetical for new concept)
        "stars_yelp":              concept.get("expected_stars") or zip_avg_stars,
        "review_count_yelp":       50,          # new restaurant prior
        "price_tier":              concept.get("price_tier", 2),
        # Review count prior — new restaurant starts small
        "review_count_computed":   0,
        # Star distribution priors — use zip averages as baseline
        "pct_1star":               0.08,
        "pct_5star":               0.35,
        "pct_negative":            0.12,
        "pct_positive":            0.65,
        "star_std":                0.9,
        "star_slope":              0.0,
        "stars_first_quartile":    zip_avg_stars,
        "stars_last_quartile":     zip_avg_stars,
        "star_delta":              0.0,
        # Sentiment priors (neutral baseline)
        "sentiment_mean":          0.3,
        "sentiment_std":           0.4,
        "sentiment_slope":         0.0,
        "sentiment_last_quartile": 0.3,
        "pct_very_positive":       0.4,
        "pct_very_negative":       0.08,
        # Engagement priors
        "useful_per_review":       0.5,
        "funny_per_review":        0.1,
        "cool_per_review":         0.2,
        "total_engagement":        40,
        "pct_engaged_reviews":     0.3,
        # Text richness priors
        "avg_review_length":       350,
        "median_review_length":    300,
        # Zip-level market context features (Real features for the improved model)
        "zip_total_restaurants":   int(zip_context.get("total_restaurants", 0)),
        "zip_avg_stars":           float(zip_context.get("avg_stars", 3.5)),
        "zip_avg_price":           float(zip_context.get("avg_price", 2.0)),
        "zip_closure_rate":        float(zip_context.get("closure_rate", 0.25)),
        # Attributes from concept input (merged with smart defaults earlier)
        "has_delivery":            int(concept.get("has_delivery") or 0),
        "has_takeout":             int(concept.get("has_takeout") or 1),
        "has_outdoor_seating":     int(concept.get("has_outdoor_seating") or 0),
        "good_for_kids":           int(concept.get("good_for_kids") or 0),
        "has_reservations":        int(concept.get("has_reservations") or 0),
        "has_wifi":                int(concept.get("has_wifi") or 0),
        "has_alcohol":             int(concept.get("has_alcohol") or 0),
        "has_tv":                  int(concept.get("has_tv") or 0),
        "good_for_groups":         int(concept.get("good_for_groups") or 0),
        # Noise level
        "noise_level":             NOISE_MAP.get(concept.get("noise_level") or "average", 1),
        # Zip-level market context features (Real features for the improved model)
        "zip_total_restaurants":   int(zip_context.get("total_restaurants", 0)),
        "zip_avg_stars":           float(zip_context.get("avg_stars", 3.5)),
        "zip_avg_price":           float(zip_context.get("avg_price", 2.0)),
        "zip_closure_rate":        float(zip_context.get("closure_rate", 0.25)),
        # Cuisine flags
        **cuisine_flags,
    }

    return [lookup.get(f, 0.0) for f in feats]


def _survival_score_interpretation(prob: float, threshold: float) -> dict:
    """Convert raw probability to a human-readable survival signal."""
    if prob >= 0.75:
        signal = "Strong survival signal — concept and location align well with open businesses."
        label = "high"
    elif prob >= threshold:
        signal = "Moderate survival signal — viable concept but some market risk."
        label = "medium"
    elif prob >= 0.40:
        signal = "Marginal survival signal — concept faces elevated closure risk at this location."
        label = "low"
    else:
        signal = "Weak survival signal — model detects significant closure risk patterns."
        label = "very_low"
    return {"label": label, "signal": signal}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Meta"])
def root():
    return {
        "service": "NJ Restaurant Market Gap API v2",
        "model_loaded": _survival_model is not None,
        "endpoints": [
            "/recommendations", "/opportunities", "/opportunity/{zip}",
            "/predict", "/meta/cuisines",
        ],
    }


@app.get("/meta/cuisines", tags=["Meta"])
def list_cuisines():
    return {"cuisines": ALL_CUISINES, "attributes": ALL_ATTRIBUTES}


@app.get("/meta/model", tags=["Meta"])
def model_info():
    """Return survival model metadata and top feature importances."""
    if not _model_metadata:
        raise HTTPException(status_code=503, detail="Survival model not loaded. Run train_survival_model.py first.")
    top_features = list(_feature_importance.items())[:20] if _feature_importance else []
    return {
        "metrics": _model_metadata["metrics"],
        "feature_count": len(_model_metadata["feature_cols"]),
        "top_features": [{"feature": k, "importance": round(v, 4)} for k, v in top_features],
        "description": _model_metadata.get("description"),
    }


@app.get("/opportunities", tags=["Core"])
def get_opportunities(
    cuisine: Optional[str] = Query(None, description="Filter + bias scoring toward this cuisine"),
    min_gap_score: float = Query(5.0, description="Minimum gap score for top cuisine gap (high-quality threshold)"),
    min_market_size: int = Query(300, description="Minimum total reviews (baseline foot traffic/data)"),
    max_risk: Optional[str] = Query(None, description="low | medium | high"),
    sort: str = Query("opportunity_score", description="opportunity_score | market_size | stars | closure_risk"),
    limit: int = Query(20, le=91),
):
    """
    Ranked list of zip codes for a restaurant concept.
    For: *"Where should I open a [cuisine] restaurant?"*
    """
    results = []
    for z in GAP_DATA:
        if cuisine:
            has_cuisine_gap = any(g["cuisine"] == cuisine for g in z["top_cuisine_gaps"])
            if not has_cuisine_gap:
                continue

        top_gap = z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0
        if cuisine:
            matched = [g for g in z["top_cuisine_gaps"] if g["cuisine"] == cuisine]
            top_gap = matched[0]["gap_score"] if matched else 0
        if top_gap < min_gap_score:
            continue

        if z["total_reviews"] < min_market_size:
            continue

        if max_risk:
            order = {"low": 0, "medium": 1, "high": 2}
            if order.get(risk_label(z["closure_rate"]), 2) > order.get(max_risk, 2):
                continue

        results.append(format_zip(z, cuisine))

    sort_keys = {
        "opportunity_score": lambda x: -x["opportunity_score"],
        "market_size":       lambda x: -x["total_reviews"],
        "stars":             lambda x: -x["avg_stars"],
        "closure_risk":      lambda x: -x["closure_rate"],
    }
    results.sort(key=sort_keys.get(sort, sort_keys["opportunity_score"]))
    return {"count": len(results), "results": results[:limit]}


@app.get("/opportunity/{zip_code}", tags=["Core"])
def get_opportunity(zip_code: str):
    """
    Full opportunity breakdown for a specific zip code.
    For: *"Is 08053 a good bet for my concept?"*
    """
    z = GAP_BY_ZIP.get(zip_code)
    if not z:
        raise HTTPException(status_code=404, detail=f"Zip code {zip_code} not found in dataset.")

    local_restaurants = [
        {
            "name": r["name"],
            "stars": r.get("stars"),
            "review_count": r.get("review_count"),
            "categories": r.get("categories"),
            "is_open": r.get("is_open"),
        }
        for r in RESTAURANTS_BY_ZIP.get(zip_code, [])
    ]
    local_restaurants.sort(key=lambda x: -(x["review_count"] or 0))

    top_gap = z["top_cuisine_gaps"][0] if z["top_cuisine_gaps"] else None
    top_attr = z["attr_gaps"][0] if z["attr_gaps"] else None

    if top_gap:
        if top_gap["local_count"] == 0:
            signal = (
                f"No {top_gap['cuisine']} restaurants exist in {zip_code}, "
                f"while {top_gap['neighbor_demand']} operate in surrounding zip codes — "
                f"strong unmet demand with zero direct competition."
            )
        else:
            signal = (
                f"Only {top_gap['local_count']} {top_gap['cuisine']} restaurant(s) in {zip_code} "
                f"serving a market where {top_gap['neighbor_demand']} nearby zips demonstrate demand. "
                f"Weak competition signal."
            )
        if top_attr:
            signal += (
                f" Adding {top_attr['attribute']} would differentiate: "
                f"only {round(top_attr['local_rate']*100)}% of local restaurants offer it "
                f"vs {round(top_attr['neighbor_avg']*100)}% regionally."
            )
    else:
        signal = "Insufficient gap data for this zip code."

    return {
        "zip": z["zip"],
        "city": z["city"],
        "opportunity_score": opportunity_score(z),
        "risk": risk_label(z["closure_rate"]),
        "market": {
            "total_restaurants": z["total_restaurants"],
            "open_restaurants": z["open_restaurants"],
            "closure_rate": z["closure_rate"],
            "avg_stars": z["avg_stars"],
            "avg_reviews": z["avg_reviews"],
            "total_reviews": z["total_reviews"],
            "avg_price_tier": z["avg_price"],
            "num_neighbors_analyzed": z["num_neighbors"],
        },
        "cuisine_gaps": z["top_cuisine_gaps"],
        "attribute_gaps": z["attr_gaps"],
        "existing_cuisines": z["existing_cuisines"],
        "signal_summary": signal,
        "local_restaurants": local_restaurants[:15],
    }


@app.get("/recommendations", tags=["Core"])
def get_recommendations(
    cuisine: Optional[str] = Query(None, description="Target cuisine type (e.g. 'Japanese', 'Pizza')"),
    max_risk: Optional[str] = Query(None, description="Max acceptable risk: low | medium | high"),
    max_price_tier: Optional[float] = Query(None, description="Max average price tier (1=budget, 4=upscale)"),
    byob: Optional[bool] = Query(None, description="Require BYOB opportunity gap"),
    delivery: Optional[bool] = Query(None, description="Require Delivery opportunity gap"),
    outdoor: Optional[bool] = Query(None, description="Require Outdoor Seating gap"),
    kid_friendly: Optional[bool] = Query(None, description="Require Kid-Friendly gap"),
    min_market_size: int = Query(0, description="Minimum total reviews in area"),
    limit: int = Query(10, le=30, description="Number of recommendations to return"),
):
    """
    Dynamic restaurant recommendations personalized to the user's concept.

    Re-scores and re-ranks all zip codes in real-time based on:
    - **cuisine**: Boosts zips where that specific cuisine has highest demand/gap
    - **max_risk**: Filters out high-closure areas if user is risk-averse
    - **max_price_tier**: Aligns recommendations with target market positioning
    - **attributes**: Weights toward areas with those specific service gaps
    - **min_market_size**: Ensures enough foot traffic in the area
    """
    risk_order = {"low": 0, "medium": 1, "high": 2}
    required_attrs = []
    if byob:         required_attrs.append("BYOB")
    if delivery:     required_attrs.append("HasTV")  # delivery proxy
    if outdoor:      required_attrs.append("OutdoorSeating")
    if kid_friendly: required_attrs.append("GoodForKids")

    results = []
    for z in GAP_DATA:
        # — Hard filters —
        if z["total_reviews"] < min_market_size:
            continue
        if max_risk:
            if risk_order.get(risk_label(z["closure_rate"]), 2) > risk_order.get(max_risk, 2):
                continue
        if max_price_tier and z.get("avg_price", 2) > max_price_tier:
            continue

        # For required attributes, check that the zip has those gaps
        present_gaps = {a["attribute"] for a in z["attr_gaps"]}
        if required_attrs and not all(a in present_gaps for a in required_attrs):
            continue

        # — Dynamic Scoring —
        # Base: cuisine-aware gap score
        if cuisine:
            matched_gaps = [g for g in z["top_cuisine_gaps"] if g["cuisine"].lower() == cuisine.lower()]
            if not matched_gaps:
                # No gap for requested cuisine = skip (no opportunity here)
                continue
            top_gap = matched_gaps[0]["gap_score"]
        else:
            top_gap = z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0

        # Market size (log-scaled)
        market_score = math.log10(z["total_reviews"] + 1) * 8

        # Stability (lower closure = higher score)
        stability_score = (1 - z["closure_rate"]) * 20

        # Attribute bonus — extra weight for each matching service gap
        attr_bonus = len(z["attr_gaps"]) * 3

        # Combined weighted score
        # 1. Market Gap Base (0-50)
        gap_contribution = min(50.0, top_gap * 6)
        
        # 2. Market Size & Stability Base (0-30)
        market_score = math.log10(z["total_reviews"] + 1) * 6
        stability_score = (1 - z["closure_rate"]) * 10
        
        # 3. Weakspot Penalty (Avoidance)
        # If closure rate is high (>30%), apply a significant penalty
        weakspot_penalty = 0
        if z["closure_rate"] > 0.30:
            weakspot_penalty = -25.0
        elif z["closure_rate"] > 0.20:
            weakspot_penalty = -10.0
            
        # 4. ML Survival Bonus (0 or +15)
        survival_bonus = 0
        survival_prob = None
        if _survival_model and cuisine:
            try:
                # Mock concept for prediction
                mock_req = {
                    "cuisine": cuisine, "price_tier": max_price_tier or 2.0,
                    "has_delivery": 1 if delivery else 0, "has_outdoor_seating": 1 if outdoor else 0,
                    "good_for_kids": 1 if kid_friendly else 0,
                }
                feat_vec = _build_feature_vector(mock_req, z)
                import numpy as np
                X = np.array([feat_vec], dtype=float)
                survival_prob = float(_survival_model.predict_proba(X)[0][1])
                if survival_prob > 0.65:
                    survival_bonus = 15.0
                elif survival_prob > 0.50:
                    survival_bonus = 5.0
            except:
                pass

        # 5. Attribute bonus (0-10)
        attr_bonus = len(z["attr_gaps"]) * 2

        # Combined Master Score (capped at 95 before jitter)
        base_master = gap_contribution + market_score + stability_score + weakspot_penalty + survival_bonus + attr_bonus
        jitter = _get_jitter(z["zip"], scale=2.5)
        
        score = max(0.1, min(99.9, round(min(95.0, base_master) + jitter, 1)))

        # — Build top gap context —
        if cuisine:
            matched_gaps = [g for g in z["top_cuisine_gaps"] if g["cuisine"].lower() == cuisine.lower()]
            top_gaps = matched_gaps + [g for g in z["top_cuisine_gaps"] if g["cuisine"].lower() != cuisine.lower()]
        else:
            top_gaps = z["top_cuisine_gaps"]

        primary = top_gaps[0]["cuisine"] if top_gaps else "General"
        competition_signal = (
            f"Zero local competition" if top_gaps and top_gaps[0]["local_count"] == 0
            else f"{top_gaps[0]['local_count']} existing competitor(s)" if top_gaps else "Unknown"
        )

        results.append({
            "zip": z["zip"],
            "city": z["city"],
            "opportunity_score": score,
            "primary_concept": primary,
            "risk": risk_label(z["closure_rate"]),
            "closure_rate": z["closure_rate"],
            "avg_stars": z["avg_stars"],
            "total_reviews": z["total_reviews"],
            "avg_price_tier": z.get("avg_price"),
            "evidence": {
                "cuisine_gap_score": round(top_gap, 2),
                "competition_signal": competition_signal,
                "neighbor_demand": top_gaps[0]["neighbor_demand"] if top_gaps else 0,
                "market_size": f"{z['total_reviews']:,} reviews",
                "attribute_opportunities": [a["attribute"] for a in z["attr_gaps"]],
                "survival_probability": round(survival_prob, 2) if survival_prob else None,
                "is_weakspot": z["closure_rate"] > 0.25,
            },
            "top_cuisine_gaps": top_gaps[:3],
        })

    # Sort by score desc
    results.sort(key=lambda x: -x["opportunity_score"])

    return {
        "query": {
            "cuisine": cuisine,
            "max_risk": max_risk,
            "max_price_tier": max_price_tier,
            "byob": byob,
            "delivery": delivery,
            "outdoor": outdoor,
            "kid_friendly": kid_friendly,
            "min_market_size": min_market_size,
        },
        "count": len(results),
        "recommendations": results[:limit],
    }


# ── /predict ──────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    zip_code: str
    cuisine: str                          # e.g. "Japanese", "Italian"
    price_tier: Optional[float] = None    # 1=budget … 4=upscale
    expected_stars: Optional[float] = None  # 1.0–5.0; leave None to use zip avg
    # Concept attributes (None = use smart default based on cuisine)
    has_delivery: Optional[int] = None
    has_takeout: Optional[int] = None
    has_outdoor_seating: Optional[int] = None
    good_for_kids: Optional[int] = None
    has_reservations: Optional[int] = None
    has_wifi: Optional[int] = None
    has_alcohol: Optional[int] = None
    has_tv: Optional[int] = None
    good_for_groups: Optional[int] = None
    noise_level: Optional[str] = None  # quiet | average | loud | very_loud

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 5:
            raise ValueError("zip_code must be a 5-digit string (e.g. '07030')")
        return v

    @field_validator("expected_stars")
    @classmethod
    def validate_stars(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (1.0 <= v <= 5.0):
            raise ValueError("expected_stars must be between 1.0 and 5.0")
        return v

    @field_validator("price_tier")
    @classmethod
    def validate_price(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (1.0 <= v <= 4.0):
            raise ValueError("price_tier must be between 1 (budget) and 4 (upscale)")
        return v

    @field_validator("noise_level")
    @classmethod
    def validate_noise(cls, v: Optional[str]) -> Optional[str]:
        valid = {"quiet", "average", "loud", "very_loud"}
        if v is not None and v not in valid:
            raise ValueError(f"noise_level must be one of: {', '.join(sorted(valid))}")
        return v


@app.post("/predict", tags=["ML"])
def predict_survival(req: PredictRequest):
    """
    Predict survival probability for a **new** restaurant concept at a given zip code.

    Uses the XGBoost survival model trained on historical Yelp data.
    For new restaurants, review-temporal features are set to zero/prior values —
    the model weights concept attributes and zip-market signals instead.

    Returns:
    - `survival_probability`: 0–1, probability the concept stays open
    - `survival_signal`: human-readable label (high / medium / low / very_low)
    - `market_context`: opportunity score + risk for that zip
    - `top_survival_factors`: top 5 features driving this prediction
    """
    if _survival_model is None:
        raise HTTPException(
            status_code=503,
            detail="Survival model not available. Run: python train_survival_model.py"
        )

    zip_context = GAP_BY_ZIP.get(req.zip_code)
    if not zip_context:
        raise HTTPException(status_code=404, detail=f"Zip code {req.zip_code} not in dataset.")

    # Merge with defaults
    cuisine_key = next((k for k in CUISINE_DEFAULTS if k.lower() == req.cuisine.lower()), None)
    defaults = CUISINE_DEFAULTS.get(cuisine_key, GLOBAL_DEFAULTS)
    
    concept_dict = req.dict()
    for key, val in defaults.items():
        if concept_dict.get(key) is None:
            concept_dict[key] = val

    # Build feature vector
    feature_vector = _build_feature_vector(concept_dict, zip_context)

    import numpy as np
    X = np.array([feature_vector], dtype=float)
    prob = float(_survival_model.predict_proba(X)[0][1])
    threshold = _model_metadata["metrics"].get("best_threshold", 0.5)
    interpretation = _survival_score_interpretation(prob, threshold)

    # Market context for this zip
    market = {
        "zip": zip_context["zip"],
        "city": zip_context["city"],
        "opportunity_score": opportunity_score(zip_context, req.cuisine),
        "risk": risk_label(zip_context["closure_rate"]),
        "closure_rate": zip_context["closure_rate"],
        "avg_stars": zip_context["avg_stars"],
        "total_reviews": zip_context["total_reviews"],
    }

    # Cuisine gap for requested cuisine
    cuisine_gap = next(
        (g for g in zip_context.get("top_cuisine_gaps", []) if g["cuisine"].lower() == req.cuisine.lower()),
        None
    )
    
    if not cuisine_gap:
        # Calculate ad-hoc gap context for any cuisine (real-time competitive analysis)
        local_biz = RESTAURANTS_BY_ZIP.get(req.zip_code, [])
        local_count = sum(1 for r in local_biz if req.cuisine.lower() in str(r.get("categories", "")).lower())
        
        # Neighbor demand proxy from general gap
        avg_gap = zip_context.get("top_cuisine_gaps", [{}])[0].get("neighbor_demand", 0)
        
        cuisine_gap = {
            "cuisine": req.cuisine,
            "local_count": local_count,
            "neighbor_demand": avg_gap,
            "gap_score": max(0, avg_gap - local_count),
        }

    # ── Per-request SHAP explanation ─────────────────────────────────────────
    # If SHAP is available we compute which features drove *this specific*
    # prediction up or down, rather than returning the same global ranking.
    feature_cols = _model_metadata["feature_cols"]
    top_factors = []

    if _shap_explainer is not None:
        try:
            import numpy as np
            # shap_values shape: (n_samples, n_features) for the positive class
            sv = _shap_explainer.shap_values(X)
            # TreeExplainer may return a list [neg_class, pos_class]
            if isinstance(sv, list):
                sv = sv[1]
            shap_row = sv[0]  # single sample
            # Pair feature names with their SHAP contributions
            pairs = sorted(
                zip(feature_cols, shap_row.tolist()),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            top_factors = [
                {
                    "feature": feat,
                    "shap_value": round(val, 4),
                    "direction": "positive" if val > 0 else "negative",
                    "global_importance": round(_feature_importance.get(feat, 0), 4),
                }
                for feat, val in pairs[:7]
            ]
        except Exception as shap_err:
            # Never crash the prediction if SHAP fails
            top_factors = [
                {"feature": k, "global_importance": round(v, 4)}
                for k, v in list(_feature_importance.items())[:7]
            ]
    elif _feature_importance:
        # Fallback: global importance when SHAP is unavailable
        top_factors = [
            {"feature": k, "global_importance": round(v, 4)}
            for k, v in list(_feature_importance.items())[:7]
        ]

    # Flag zero-importance cuisines so users know prediction is
    # attribute/zip-driven rather than cuisine-specific
    cuisine_key_lower = req.cuisine.lower().replace(" ", "_")
    cuisine_col = f"cuisine_{cuisine_key_lower}"
    cuisine_importance = _feature_importance.get(cuisine_col, 0) if _feature_importance else None
    cuisine_warning = None
    if cuisine_importance is not None and cuisine_importance == 0:
        cuisine_warning = (
            f"The '{req.cuisine}' cuisine has zero model importance in the training data "
            "(too few NJ examples). Prediction reflects zip market + chosen attributes only."
        )

    return {
        "zip_code": req.zip_code,
        "cuisine": req.cuisine,
        "concept_applied": {k: v for k, v in concept_dict.items() if k not in ["zip_code", "cuisine"]},
        "survival_probability": round(prob, 4),
        "survival_signal": interpretation,
        "market_context": market,
        "cuisine_gap": cuisine_gap,
        "top_survival_factors": top_factors,
        "cuisine_model_warning": cuisine_warning,
        "shap_available": _shap_explainer is not None,
        "model_metrics": {
            "cv_roc_auc": _model_metadata["metrics"]["cv_roc_auc_mean"],
            "threshold_used": threshold,
        },
    }