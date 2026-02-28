from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

with open(DATA_DIR / "recommendation_report.json") as f:
    RECOMMENDATION_REPORT: dict = json.load(f)

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

def _load_survival_model():
    """Lazy-load the XGBoost survival model. Fails gracefully if not present."""
    global _survival_model, _model_metadata, _feature_importance

    meta_path = MODEL_DIR / "model_metadata.json"
    model_path = MODEL_DIR / "survival_model.json"
    imp_path = MODEL_DIR / "feature_importance.json"

    if not meta_path.exists() or not model_path.exists():
        print("⚠  Survival model not found — /predict will return 503.")
        print("   Run: python train_survival_model.py")
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
    attr_bonus = len(z["attr_gaps"]) * 5
    return round(top_gap * 0.6 + market_size * 2 + attr_bonus, 2)


def risk_label(closure_rate: float) -> str:
    if closure_rate < 0.2:  return "low"
    if closure_rate < 0.35: return "medium"
    return "high"


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

    # Base lookup — defaults to zip-market-level priors for temporal features
    lookup = {
        # Yelp base (hypothetical)
        "stars_yelp":              concept.get("expected_stars", zip_avg_stars),
        "review_count_yelp":       50,                  # new restaurant prior
        "price_tier":              concept.get("price_tier", 2),
        # Temporal priors (new restaurant — no history yet)
        "review_count_computed":   0,
        "lifespan_days":           0,
        "review_velocity_30d":     0,
        "review_velocity_90d":     0,
        "reviews_per_month":       0,
        # Star distribution priors — inherit zip avg
        "pct_1star":               0.08,
        "pct_5star":               0.35,
        "pct_negative":            0.12,
        "pct_positive":            0.65,
        "star_std":                0.9,
        "star_slope":              0.0,
        "stars_first_quartile":    zip_avg_stars,
        "stars_last_quartile":     zip_avg_stars,
        "star_delta":              0.0,
        # Sentiment priors
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
        # Attributes from concept input
        "has_delivery":            int(concept.get("has_delivery", 0)),
        "has_takeout":             int(concept.get("has_takeout", 1)),
        "has_outdoor_seating":     int(concept.get("has_outdoor_seating", 0)),
        "good_for_kids":           int(concept.get("good_for_kids", 0)),
        "has_reservations":        int(concept.get("has_reservations", 0)),
        "has_wifi":                int(concept.get("has_wifi", 0)),
        "has_alcohol":             int(concept.get("has_alcohol", 0)),
        "has_tv":                  int(concept.get("has_tv", 0)),
        "good_for_groups":         int(concept.get("good_for_groups", 0)),
        # Noise level
        "noise_level":             NOISE_MAP.get(concept.get("noise_level", "average"), 1),
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
            "/opportunities", "/opportunity/{zip}", "/search",
            "/weakspots", "/predict", "/meta/cuisines", "/recommendations",
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
    min_gap_score: float = Query(0, description="Minimum gap score for top cuisine gap"),
    min_market_size: int = Query(0, description="Minimum total reviews (proxy for foot traffic)"),
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


@app.get("/search", tags=["Core"])
def search_opportunities(
    cuisine: Optional[str] = Query(None),
    byob: Optional[bool] = Query(None),
    delivery: Optional[bool] = Query(None),
    outdoor: Optional[bool] = Query(None),
    late_night: Optional[bool] = Query(None),
    kid_friendly: Optional[bool] = Query(None),
    max_price_tier: Optional[float] = Query(None),
    min_market_size: int = Query(500),
    max_risk: Optional[str] = Query(None),
    limit: int = Query(15, le=91),
):
    """
    Multi-filter concept search.
    For: *"I want to open a mid-range BYOB Thai spot — where?"*
    """
    attr_map = {
        "BYOB": byob, "Delivery": delivery, "Outdoor Seating": outdoor,
        "Late Night": late_night, "Kid-Friendly": kid_friendly,
    }
    required_attrs = [attr for attr, val in attr_map.items() if val is True]

    results = []
    for z in GAP_DATA:
        if z["total_reviews"] < min_market_size:
            continue
        if max_risk:
            order = {"low": 0, "medium": 1, "high": 2}
            if order.get(risk_label(z["closure_rate"]), 2) > order.get(max_risk, 2):
                continue
        if max_price_tier and z["avg_price"] > max_price_tier:
            continue
        if cuisine:
            if not any(g["cuisine"] == cuisine for g in z["top_cuisine_gaps"]):
                continue
        present_attr_gaps = {a["attribute"] for a in z["attr_gaps"]}
        if required_attrs and not all(a in present_attr_gaps for a in required_attrs):
            continue
        results.append(format_zip(z, cuisine))

    results.sort(key=lambda x: -x["opportunity_score"])
    return {"count": len(results), "results": results[:limit]}


@app.get("/weakspots", tags=["Core"])
def get_weakspots(
    cuisine: Optional[str] = Query(None),
    min_closure_rate: float = Query(0.25),
    min_existing: int = Query(1),
    min_avg_stars: float = Query(0),
    max_avg_stars: float = Query(5.0),
    limit: int = Query(15, le=91),
):
    """
    Where is existing competition weak?
    For: *"Where is Italian failing — a BETTER Italian restaurant would win."*
    """
    results = []
    for z in GAP_DATA:
        if z["closure_rate"] < min_closure_rate:
            continue
        if z["avg_stars"] < min_avg_stars or z["avg_stars"] > max_avg_stars:
            continue
        if cuisine:
            existing_count = z["existing_cuisines"].get(cuisine, 0)
            if existing_count < min_existing:
                continue
            gap = next((g for g in z["top_cuisine_gaps"] if g["cuisine"] == cuisine), None)
        else:
            gap = z["top_cuisine_gaps"][0] if z["top_cuisine_gaps"] else None
        if not gap:
            continue

        results.append({
            **format_zip(z, cuisine),
            "existing_count": z["existing_cuisines"].get(cuisine, 0) if cuisine else None,
            "weak_competitor_signal": gap["local_count"] > 0 and gap["gap_score"] > 5,
            "gap_for_cuisine": gap,
        })

    results.sort(key=lambda x: -(x["closure_rate"] * x["opportunity_score"]))
    return {"count": len(results), "results": results[:limit]}


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
    if byob:        required_attrs.append("BYOB")
    if delivery:    required_attrs.append("HasTV")  # delivery proxy
    if outdoor:     required_attrs.append("OutdoorSeating")
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

        # Combined weighted score (0–100)
        score = min(100, round((top_gap * 5) + market_score + stability_score + attr_bonus, 1))

        # — Build top gap context —
        if cuisine:
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
    price_tier: Optional[float] = 2.0    # 1=budget … 4=upscale
    expected_stars: Optional[float] = None  # leave None to use zip avg as prior
    # Concept attributes (all default to 0 / not offered)
    has_delivery: Optional[int] = 0
    has_takeout: Optional[int] = 1
    has_outdoor_seating: Optional[int] = 0
    good_for_kids: Optional[int] = 0
    has_reservations: Optional[int] = 0
    has_wifi: Optional[int] = 0
    has_alcohol: Optional[int] = 0
    has_tv: Optional[int] = 0
    good_for_groups: Optional[int] = 0
    noise_level: Optional[str] = "average"  # quiet | average | loud | very_loud


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

    # Build feature vector
    feature_vector = _build_feature_vector(req.dict(), zip_context)

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
        (g for g in zip_context["top_cuisine_gaps"] if g["cuisine"].lower() == req.cuisine.lower()),
        None
    )

    # Top survival factors from global feature importance
    feature_cols = _model_metadata["feature_cols"]
    top_factors = [
        {"feature": k, "importance": round(v, 4)}
        for k, v in list(_feature_importance.items())[:5]
    ] if _feature_importance else []

    return {
        "zip_code": req.zip_code,
        "cuisine": req.cuisine,
        "survival_probability": round(prob, 4),
        "survival_signal": interpretation,
        "market_context": market,
        "cuisine_gap": cuisine_gap,
        "top_survival_factors": top_factors,
        "model_metrics": {
            "cv_roc_auc": _model_metadata["metrics"]["cv_roc_auc_mean"],
            "threshold_used": threshold,
        },
    }