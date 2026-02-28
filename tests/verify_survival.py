import json
import math
import numpy as np
from pathlib import Path
import xgboost as xgb

# Path setup
BASE_DIR = Path(__file__).parent.parent
MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

def load_data():
    with open(MODEL_DIR / "model_metadata.json") as f:
        meta = json.load(f)
    with open(DATA_DIR / "gap_analysis.json") as f:
        gap_data = json.load(f)
    
    model = xgb.Booster()
    model.load_model(str(MODEL_DIR / "survival_model.json"))
    
    return meta, gap_data, model

def mock_predict(zip_code, cuisine, meta, gap_data, model):
    zip_context = next((z for z in gap_data if z["zip"] == zip_code), None)
    if not zip_context:
        return None
    
    # Feature engineering (Simplified version of main.py logic)
    feats = meta["feature_cols"]
    lookup = {
        "stars_yelp": 4.0,
        "review_count_yelp": 50,
        "price_tier": 2,
        "zip_total_restaurants": zip_context.get("total_restaurants", 0),
        "zip_avg_stars": zip_context.get("avg_stars", 3.5),
        "zip_avg_price": zip_context.get("avg_price", 2.0),
        "zip_closure_rate": zip_context.get("closure_rate", 0.2),
        "has_delivery": 1,
        "has_takeout": 1,
        "good_for_kids": 1,
        "has_reservations": 0,
        "has_wifi": 1,
        "has_alcohol": 0,
        "has_tv": 0,
        "good_for_groups": 1,
        "noise_level": 1,
    }
    
    # Cuisine flags
    for feat in feats:
        if feat.startswith("cuisine_"):
            c = feat.replace("cuisine_", "").replace("_", " ")
            lookup[feat] = 1 if c.lower() == cuisine.lower() else 0
            
    vector = [float(lookup.get(f, 0.0)) for f in feats]
    dmat = xgb.DMatrix(np.array([vector]), feature_names=feats)
    prob = model.predict(dmat)[0]
    return prob

def run_tests():
    meta, gap_data, model = load_data()
    
    # Select a few NJ zip codes from the dataset
    test_zips = [z["zip"] for z in gap_data[:5]]
    test_cuisines = ["Pizza", "Japanese", "Mexican", "Italian"]
    
    print(f"Testing Survival Model Consistency across {len(test_zips)} zips and {len(test_cuisines)} cuisines...")
    print(f"{'Zip':<8} | {'City':<15} | {'Cuisine':<12} | {'Survival Prob':<15} | {'Density'}")
    print("-" * 80)
    
    for z in test_zips:
        zip_ctx = next(zc for zc in gap_data if zc["zip"] == z)
        city = zip_ctx.get("city", "Unknown")
        density = zip_ctx.get("total_restaurants", 0)
        
        for c in test_cuisines:
            prob = mock_predict(z, c, meta, gap_data, model)
            if prob is not None:
                # XGBoost predict for binary classification returns probability of class 1
                # but if not using predict_proba it's the raw margin or prob depending on objective
                print(f"{z:<8} | {city[:15]:<15} | {c:<12} | {float(prob):>13.4f} | {density:>7}")

if __name__ == "__main__":
    run_tests()
