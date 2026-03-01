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
    if closure_rate < 0.20: return "low"
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
    
    # --- Market Baseline Computations ---
    # We want to know how strict/long-winded the neighborhood is.
    local_biz = RESTAURANTS_BY_ZIP.get(zip_context.get("zip", ""), [])
    
    # Calculate text length baselines dynamically
    lengths = [r.get("avg_review_length") for r in local_biz if r.get("avg_review_length")]
    zip_avg_len = sum(lengths) / len(lengths) if lengths else 350.0
    
    # Calculate sentiment baselines dynamically
    sentiments = [r.get("sentiment_mean") for r in local_biz if r.get("sentiment_mean") is not None]
    zip_sentiment_mean = sum(sentiments) / len(sentiments) if sentiments else 0.3
    
    # Star trends baselines (if needed)

    lookup = {
        # Yelp base (hypothetical for new concept)
        "price_tier":              concept.get("price_tier", 2),
        
        # Sentiment priors (Market baseline)
        "sentiment_mean":          zip_sentiment_mean,
        "sentiment_std":           0.4,
        "sentiment_slope":         0.0,
        
        # Text richness priors (Market baseline)
        "avg_review_length":       zip_avg_len,
        "median_review_length":    zip_avg_len * 0.9,
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
    min_gap_score: float = Query(0.0, description="Minimum gap score for top cuisine gap (0 = show all)"),
    min_market_size: int = Query(0, description="Minimum total reviews (0 = show all areas)"),
    risk_levels: Optional[str] = Query(None, description="Comma-separated accepted risks: low,medium,high"),
    sort: str = Query("opportunity_score", description="opportunity_score | market_size | stars | closure_risk | distance_to_target"),
    target_zip: Optional[str] = Query(None, description="Zip code to calculate distance from when sorting by distance"),
    limit: int = Query(91, le=91),
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

        if risk_levels:
            accepted_risks = [r.strip().lower() for r in risk_levels.split(",")]
            if risk_label(z["closure_rate"]) not in accepted_risks:
                continue

        results.append(format_zip(z, cuisine))

    def _geo_dist(zip_a: str, zip_b: str) -> float:
        a = ZIP_COORDS.get(zip_a, (39.9, -75.0))
        b = ZIP_COORDS.get(zip_b, (39.9, -75.0))
        # Simple Euclidean distance approximation for sorting
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    sort_keys = {
        "opportunity_score": lambda x: -x["opportunity_score"],
        "market_size":       lambda x: -x["total_reviews"],
        "stars":             lambda x: -x["avg_stars"],
        "closure_risk":      lambda x: -x["closure_rate"],
        "distance_to_target": lambda x: _geo_dist(x["zip"], target_zip) if target_zip else 0,
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


# ── Cuisine Synonym Families (Idea #5) ─────────────────────────────────────────
# Maps a requested cuisine to a list of closely related cuisines whose gaps
# "count" as exact matches for the requested concept.
CUISINE_SYNONYMS: dict[str, list[str]] = {
    "pizza":          ["italian"],
    "italian":        ["pizza", "mediterranean"],
    "japanese":       ["sushi", "korean", "asian"],
    "sushi":          ["japanese", "asian"],
    "korean":         ["japanese", "asian"],
    "chinese":        ["asian", "vietnamese"],
    "vietnamese":     ["asian", "chinese", "thai"],
    "thai":           ["asian", "vietnamese"],
    "asian":          ["japanese", "chinese", "vietnamese", "thai", "korean", "sushi"],
    "mediterranean":  ["greek", "middle eastern", "italian"],
    "greek":          ["mediterranean", "middle eastern"],
    "middle eastern": ["mediterranean", "greek"],
    "mexican":        ["spanish", "latin", "caribbean"],
    "spanish":        ["mexican", "latin"],
    "latin":          ["mexican", "spanish", "caribbean"],
    "caribbean":      ["latin", "mexican"],
    "american":       ["burgers", "sandwiches", "barbecue"],
    "burgers":        ["american", "sandwiches"],
    "sandwiches":     ["american", "burgers"],
    "barbecue":       ["american"],
    "vegan":          ["salad", "breakfast", "mediterranean"],
    "seafood":        ["sushi", "japanese"],
    "indian":         ["middle eastern", "mediterranean"],
}


# ── County Mapping for all 91 dataset zips ───────────────────────────────────
ZIP_COUNTY: dict[str, str] = {
    # Camden County
    "08002": "Camden", "08003": "Camden", "08007": "Camden", "08012": "Camden",
    "08021": "Camden", "08026": "Camden", "08029": "Camden", "08031": "Camden",
    "08033": "Camden", "08034": "Camden", "08035": "Camden", "08045": "Camden",
    "08049": "Camden", "08052": "Camden", "08059": "Camden", "08078": "Camden",
    "08081": "Camden", "08083": "Camden", "08084": "Camden", "08091": "Camden",
    "08102": "Camden", "08103": "Camden", "08104": "Camden", "08105": "Camden",
    "08106": "Camden", "08107": "Camden", "08108": "Camden",
    # Burlington County
    "08010": "Burlington", "08016": "Burlington", "08022": "Burlington",
    "08036": "Burlington", "08046": "Burlington", "08048": "Burlington",
    "08054": "Burlington", "08055": "Burlington", "08057": "Burlington",
    "08060": "Burlington", "08065": "Burlington", "08068": "Burlington",
    "08075": "Burlington", "08077": "Burlington", "08088": "Burlington",
    "08505": "Burlington", "08518": "Burlington", "08554": "Burlington",
    # Gloucester County
    "08004": "Gloucester", "08009": "Gloucester", "08018": "Gloucester",
    "08020": "Gloucester", "08027": "Gloucester", "08028": "Gloucester",
    "08030": "Gloucester", "08051": "Gloucester", "08062": "Gloucester",
    "08063": "Gloucester", "08066": "Gloucester", "08071": "Gloucester",
    "08080": "Gloucester", "08085": "Gloucester", "08086": "Gloucester",
    "08089": "Gloucester", "08090": "Gloucester", "08093": "Gloucester",
    "08094": "Gloucester", "08096": "Gloucester", "08097": "Gloucester",
    "08312": "Gloucester", "08322": "Gloucester",
    # Salem County
    "08069": "Salem", "08070": "Salem", "08079": "Salem",
    "08098": "Salem", "08318": "Salem", "08328": "Salem", "08344": "Salem",
    # Mercer County
    "08530": "Mercer", "08608": "Mercer", "08609": "Mercer", "08610": "Mercer",
    "08611": "Mercer", "08618": "Mercer", "08619": "Mercer", "08628": "Mercer",
    "08629": "Mercer", "08638": "Mercer", "08648": "Mercer",
    # Pennsauken / Camden City
    "08109": "Camden", "08110": "Camden",
}

# Approximate lat/lon centroids per zip (used by MMR geographic penalty)
ZIP_COORDS: dict[str, tuple[float, float]] = {
    "08002": (39.934, -74.998), "08003": (39.901, -74.953), "08004": (39.780, -74.877),
    "08007": (39.864, -75.063), "08009": (39.791, -74.935), "08010": (40.063, -74.916),
    "08012": (39.794, -75.063), "08016": (40.080, -74.862), "08018": (39.780, -75.015),
    "08020": (39.812, -75.118), "08021": (39.802, -74.981), "08022": (40.017, -74.705),
    "08026": (39.836, -74.967), "08027": (39.833, -75.116), "08028": (39.703, -75.112),
    "08029": (39.834, -75.072), "08030": (39.889, -75.124), "08031": (39.868, -75.094),
    "08033": (39.898, -75.033), "08034": (39.916, -74.993), "08035": (39.878, -75.065),
    "08036": (40.002, -74.828), "08037": (39.639, -74.800), "08043": (39.859, -74.961),
    "08045": (39.868, -75.028), "08046": (40.025, -74.893), "08048": (39.956, -74.647),
    "08049": (39.858, -75.039), "08051": (39.768, -75.194), "08052": (39.952, -74.999),
    "08053": (39.896, -74.918), "08054": (39.964, -74.918), "08055": (39.877, -74.823),
    "08057": (39.972, -75.016), "08059": (39.876, -75.086), "08060": (39.995, -74.790),
    "08062": (39.738, -75.232), "08063": (39.858, -75.178), "08065": (40.002, -75.022),
    "08066": (39.837, -75.248), "08068": (39.957, -74.681), "08069": (39.727, -75.468),
    "08070": (39.659, -75.517), "08071": (39.733, -75.134), "08075": (40.002, -74.936),
    "08077": (40.001, -74.993), "08078": (39.857, -75.069), "08079": (39.574, -75.471),
    "08080": (39.745, -75.103), "08081": (39.759, -75.006), "08083": (39.846, -75.019),
    "08084": (39.832, -75.019), "08085": (39.750, -75.313), "08086": (39.857, -75.197),
    "08088": (39.836, -74.686), "08089": (39.779, -74.963), "08090": (39.813, -75.155),
    "08091": (39.803, -75.002), "08093": (39.870, -75.143), "08094": (39.668, -75.021),
    "08096": (39.841, -75.152), "08097": (39.824, -75.148), "08098": (39.659, -75.323),
    "08102": (39.943, -75.116), "08103": (39.939, -75.107), "08104": (39.916, -75.116),
    "08105": (39.955, -75.094), "08106": (39.892, -75.073), "08107": (39.901, -75.077),
    "08108": (39.917, -75.071), "08109": (39.975, -75.058), "08110": (39.981, -75.057),
    "08312": (39.658, -75.086), "08318": (39.594, -75.134), "08322": (39.634, -75.059),
    "08328": (39.577, -75.037), "08344": (39.596, -75.038), "08505": (40.142, -74.716),
    "08518": (40.121, -74.808), "08530": (40.364, -74.943), "08554": (40.116, -74.792),
    "08608": (40.219, -74.759), "08609": (40.223, -74.728), "08610": (40.193, -74.710),
    "08611": (40.214, -74.741), "08618": (40.239, -74.804), "08619": (40.214, -74.661),
    "08628": (40.264, -74.803), "08629": (40.219, -74.741), "08638": (40.248, -74.797),
    "08648": (40.288, -74.740),
}


@app.get("/recommendations", tags=["Core"])
def get_recommendations(
    cuisine: Optional[str] = Query(None, description="Target cuisine type (e.g. 'Japanese', 'Pizza')"),
    risk_levels: Optional[str] = Query(None, description="Comma-separated accepted risks: low,medium,high"),
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

    # Idea #5 — build the set of accepted cuisines (requested + synonyms)
    cuisine_family: set[str] = set()
    if cuisine:
        cuisine_family.add(cuisine.lower())
        for syn in CUISINE_SYNONYMS.get(cuisine.lower(), []):
            cuisine_family.add(syn.lower())

    # Idea #2 — tolerance buffers so near-misses don't become relaxed
    PRICE_TOLERANCE  = 0.5   # avg_price may exceed max by this much and still be exact
    RISK_TOLERANCE   = 0.05  # closure_rate may exceed the risk boundary by 5 pp

    # Idea #3 — total-penalty threshold: if cumulative penalty is small, call it exact
    EXACT_PENALTY_THRESHOLD = -10.0

    # Pre-compute sorted gap list for fast percentile lookup
    import bisect
    _all_top_gaps_sorted = sorted(
        z2["top_cuisine_gaps"][0]["gap_score"] if z2["top_cuisine_gaps"] else 0
        for z2 in GAP_DATA
    )
    _n_gaps = len(_all_top_gaps_sorted)

    results = []
    for z in GAP_DATA:
        is_exact = True
        match_issues = []
        penalty = 0.0

        # — Soft filters (Relaxed Matching) —
        if z["total_reviews"] < min_market_size:
            continue  # Keep minimum market size as a hard filter

        # Idea #2 — Risk toggle logic
        if risk_levels:
            accepted_risks = [r.strip().lower() for r in risk_levels.split(",")]
            z_risk = risk_label(z["closure_rate"])
            if z_risk not in accepted_risks:
                continue

        # Idea #2 — Price with tolerance buffer
        if max_price_tier:
            z_price = z.get("avg_price", 2.0)
            if z_price > max_price_tier:
                overshoot = z_price - max_price_tier
                if overshoot <= PRICE_TOLERANCE:
                    penalty -= 5.0   # small buffer penalty
                    match_issues.append(f"Slightly above price target ({z_price:.1f} vs requested ≤{max_price_tier})")
                else:
                    is_exact = False
                    penalty -= 15.0
                    match_issues.append(f"Average price tier is higher than expected")

        # For required attributes, check that the zip has those gaps
        present_gaps = {a["attribute"] for a in z["attr_gaps"]}
        missing_attrs = [req for req in required_attrs if req not in present_gaps]

        if missing_attrs:
            # Idea #4 — "OR" / majority logic: if more than half are fulfilled, don't flip to relaxed
            fulfilled = len(required_attrs) - len(missing_attrs)
            majority_met = fulfilled >= len(required_attrs) / 2 if required_attrs else True

            # Check confidence based on local sample size of the requested cuisine
            low_confidence = False
            if cuisine:
                local_biz = RESTAURANTS_BY_ZIP.get(z["zip"], [])
                local_cuisine_count = sum(
                    1 for r in local_biz
                    if any(c in str(r.get("categories", "")).lower() for c in cuisine_family)
                )
                if local_cuisine_count < 3:
                    low_confidence = True

            if low_confidence:
                # Not enough data — tiny penalty
                penalty -= 2.0 * len(missing_attrs)
                match_issues.append(
                    f"Unconfirmed gaps due to low local sample size ({local_cuisine_count} {cuisine} places): {', '.join(missing_attrs)}"
                )
            elif majority_met and len(required_attrs) >= 2:
                # Idea #4 — majority fulfilled, treat as near-exact
                penalty -= 5.0 * len(missing_attrs)
                match_issues.append(f"Most requested service gaps present; missing: {', '.join(missing_attrs)}")
            else:
                is_exact = False
                penalty -= 8.0 * len(missing_attrs)
                match_issues.append(f"Missing validated service gaps: {', '.join(missing_attrs)}")

        # — Dynamic Scoring —
        # Idea #1 — Cuisine matching: accept any positive gap in the cuisine family
        if cuisine:
            # First: exact cuisine name match
            matched_gaps = [g for g in z["top_cuisine_gaps"] if g["cuisine"].lower() == cuisine.lower()]
            # Second: synonym family match (Idea #5)
            if not matched_gaps:
                matched_gaps = [
                    g for g in z["top_cuisine_gaps"]
                    if g["cuisine"].lower() in cuisine_family
                ]
                if matched_gaps:
                    top_gap = matched_gaps[0]["gap_score"]
                    match_issues.append(f"Matched via related cuisine: {matched_gaps[0]['cuisine']}")
                else:
                    # Idea #1 — Not in top gaps but check if ANY positive gap exists
                    local_biz = RESTAURANTS_BY_ZIP.get(z["zip"], [])
                    local_count = sum(
                        1 for r in local_biz
                        if any(c in str(r.get("categories", "")).lower() for c in cuisine_family)
                    )
                    avg_gap = z.get("top_cuisine_gaps", [{}])[0].get("neighbor_demand", 0) if z.get("top_cuisine_gaps") else 0
                    computed_gap = max(0, avg_gap - local_count)
                    if computed_gap > 0:
                        # There IS some gap, just smaller — accept as low-penalty relaxed
                        is_exact = False
                        penalty -= 8.0
                        match_issues.append("Cuisine gap exists but not among strongest in this area")
                        top_gap = computed_gap
                    else:
                        # Truly no gap signal
                        is_exact = False
                        penalty -= 12.0
                        match_issues.append("No measurable cuisine gap detected in this area")
                        top_gap = 0
            else:
                top_gap = matched_gaps[0]["gap_score"]
        else:
            top_gap = z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0

        # ── Redesigned Scoring Formula ──────────────────────────────────────────
        # Use percentile-rank normalization so that extreme outliers (e.g. Camden
        # with gap scores of 300-491) don't dominate at the expense of all other
        # cities. Each zip's gap is scored relative to the full dataset.

        # 1. Percentile-normalized cuisine gap contribution (0–50 pts)
        #    Each zip's gap is ranked against the full dataset distribution.
        #    A gap at the 90th percentile → 45 pts; at the 50th → 25 pts.
        gap_percentile = bisect.bisect_right(_all_top_gaps_sorted, top_gap) / _n_gaps
        gap_contribution = gap_percentile * 50.0  # maps to 0–50 pts

        # 2. Market size — supporting context (reduced weight vs. gap)
        market_score = math.log10(z["total_reviews"] + 1) * 4

        # 3. Stability — lower closure = bonus
        stability_score = (1 - z["closure_rate"]) * 8

        # 4. Weakspot Penalty
        weakspot_penalty = 0
        if z["closure_rate"] > 0.30:
            weakspot_penalty = -25.0
        elif z["closure_rate"] > 0.20:
            weakspot_penalty = -10.0

        # 5. ML Survival Bonus (0, +8, or +15)
        survival_bonus = 0
        survival_prob = None
        if _survival_model and cuisine:
            try:
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
                    survival_bonus = 8.0
            except:
                pass

        # 6. Attribute gap bonus (tie-breaker weight only)
        attr_bonus = len(z["attr_gaps"]) * 1.5

        # Combined Master Score — cap raised to 99 so big gaps can fully surface
        base_master = gap_contribution + market_score + stability_score + weakspot_penalty + survival_bonus + attr_bonus + penalty
        jitter = _get_jitter(z["zip"], scale=1.5)   # reduced jitter so gap drives ranking
        score = max(0.1, min(99.9, round(min(99.0, base_master) + jitter, 1)))

        # Idea #3 — Penalty threshold: if cumulative penalty is small, still call it exact
        if penalty < 0 and penalty >= EXACT_PENALTY_THRESHOLD:
            is_exact = True

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
            "match_score": score,
            "opportunity_score": opportunity_score(z, cuisine),
            "match_type": "exact" if is_exact else "relaxed",
            "match_issues": match_issues,
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
    results.sort(key=lambda x: -x["match_score"])

    # ── Step 1: Group by city FIRST ───────────────────────────────────────────
    # We group BEFORE MMR so Camden's 4 zip codes become ONE city candidate.
    # Previously, each zip consumed a separate MMR/county slot, saturating the
    # results with sub-neighborhoods of the same city.
    city_pool: dict[str, dict] = {}
    for r in results:
        city = r["city"]
        if city not in city_pool:
            city_pool[city] = {
                **r,
                "zips": [{
                    "zip": r["zip"],
                    "match_score": r["match_score"],
                    "opportunity_score": r["opportunity_score"],
                    "match_type": r["match_type"],
                    "match_issues": r["match_issues"],
                    "risk": r["risk"],
                    "total_reviews": r["total_reviews"],
                    "avg_price_tier": r["avg_price_tier"],
                    "evidence": r["evidence"],
                    "top_cuisine_gaps": r["top_cuisine_gaps"],
                }],
                "total_reviews": r["total_reviews"],
                "_rep_zip": r["zip"],   # best-scoring zip used for distance calc
            }
        else:
            city_pool[city]["zips"].append({
                "zip": r["zip"],
                "match_score": r["match_score"],
                "opportunity_score": r["opportunity_score"],
                "match_type": r["match_type"],
                "match_issues": r["match_issues"],
                "risk": r["risk"],
                "total_reviews": r["total_reviews"],
                "avg_price_tier": r["avg_price_tier"],
                "evidence": r["evidence"],
                "top_cuisine_gaps": r["top_cuisine_gaps"],
            })
            existing_attrs = set(city_pool[city]["evidence"]["attribute_opportunities"])
            for attr in r["evidence"]["attribute_opportunities"]:
                existing_attrs.add(attr)
            city_pool[city]["evidence"]["attribute_opportunities"] = list(existing_attrs)
            city_pool[city]["total_reviews"] += r["total_reviews"]

    # Ordered by best-zip score (results was already sorted)
    city_candidates = list(city_pool.values())

    # ── Step 2: MMR + County Cap — on city-level candidates ───────────────────
    RELEVANCE_WEIGHT = 0.60
    DIVERSITY_WEIGHT = 0.40

    # Per-county caps: Camden County is intentionally limited to 1 city
    # because it contains 27 of the 91 zip codes and would otherwise dominate.
    # All other counties default to 2 cities each.
    COUNTY_CAPS: dict[str, int] = {
        "Camden":     0,   # excluded — too many zip codes, dominates results
        "Gloucester": 2,
        "Burlington": 2,
        "Salem":      2,
        "Mercer":     2,
    }
    DEFAULT_COUNTY_CAP = 2

    def _geo_dist(zip_a: str, zip_b: str) -> float:
        a = ZIP_COORDS.get(zip_a, (39.9, -75.0))
        b = ZIP_COORDS.get(zip_b, (39.9, -75.0))
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    max_score   = city_candidates[0]["match_score"] if city_candidates else 1
    min_score   = city_candidates[-1]["match_score"] if city_candidates else 0
    score_range = max(max_score - min_score, 0.001)

    selected:      list[dict] = []
    selected_zips: list[str]  = []
    county_counts: dict[str, int] = {}
    remaining = list(city_candidates)

    while remaining and len(selected) < limit:
        best     = None
        best_mmr = float("-inf")

        for cand in remaining:
            rep    = cand["_rep_zip"]
            county = ZIP_COUNTY.get(rep, "Unknown")
            cap    = COUNTY_CAPS.get(county, DEFAULT_COUNTY_CAP)

            if county_counts.get(county, 0) >= cap:
                continue  # county cap

            relevance = (cand["match_score"] - min_score) / score_range

            if not selected_zips:
                max_sim = 0.0
            else:
                sims = [1.0 / (1.0 + _geo_dist(rep, sz)) for sz in selected_zips]
                max_sim = max(sims)

            mmr = RELEVANCE_WEIGHT * relevance - DIVERSITY_WEIGHT * max_sim
            if mmr > best_mmr:
                best_mmr = mmr
                best = cand

        if best is None:
            best = remaining[0]   # fallback if all counties capped

        selected.append(best)
        selected_zips.append(best["_rep_zip"])
        county = ZIP_COUNTY.get(best["_rep_zip"], "Unknown")
        county_counts[county] = county_counts.get(county, 0) + 1
        remaining.remove(best)

    # Re-sort selected cities by score descending so UI shows best first
    selected.sort(key=lambda x: -x["match_score"])

    # Strip internal helper key
    grouped = [{k: v for k, v in c.items() if k != "_rep_zip"} for c in selected]

    return {
        "query": {
            "cuisine": cuisine,
            "risk_levels": risk_levels,
            "max_price_tier": max_price_tier,
            "byob": byob,
            "delivery": delivery,
            "outdoor": outdoor,
            "kid_friendly": kid_friendly,
            "min_market_size": min_market_size,
        },
        "count": len(grouped),
        "total_analyzed": len(GAP_DATA),
        "recommendations": grouped[:limit],
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
        "shap_available": "shap_value" in top_factors[0] if top_factors else False,
        "cuisine_model_warning": cuisine_warning,
        "model_metrics": {
            "cv_roc_auc": _model_metadata["metrics"]["cv_roc_auc_mean"],
            "threshold_used": threshold,
        },
    }