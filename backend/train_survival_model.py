"""
train_survival_model.py
=======================
Trains an XGBoost binary classifier to predict restaurant survival (is_open).
Input: review_features.json (output of compute_review_features.py)
Output:
  - models/survival_model.json   — the trained XGBoost model
  - models/feature_importance.json
  - models/model_metadata.json   — thresholds, feature list, eval metrics

Usage
-----
    python train_survival_model.py \
        --input   data/review_features.json \
        --out_dir models/

Dependencies
------------
    pip install xgboost scikit-learn pandas numpy shap
"""

import argparse
import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    roc_auc_score, classification_report,
    average_precision_score, confusion_matrix,
)
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

warnings.filterwarnings("ignore")


# ── Feature config ────────────────────────────────────────────────────────────

NUMERIC_FEATURES = [
    # yelp base
    "stars_yelp", "review_count_yelp", "price_tier",
    # review temporal
    "review_count_computed", "lifespan_days", "review_velocity_30d",
    "review_velocity_90d", "reviews_per_month",
    # star trend
    "pct_1star", "pct_5star", "pct_negative", "pct_positive",
    "star_std", "star_slope", "stars_first_quartile", "stars_last_quartile", "star_delta",
    # sentiment
    "sentiment_mean", "sentiment_std", "sentiment_slope",
    "sentiment_last_quartile", "pct_very_positive", "pct_very_negative",
    # engagement
    "useful_per_review", "funny_per_review", "cool_per_review",
    "total_engagement", "pct_engaged_reviews",
    # text
    "avg_review_length", "median_review_length",
    # attributes
    "has_delivery", "has_takeout", "has_outdoor_seating", "good_for_kids",
    "has_reservations", "has_wifi", "has_alcohol", "has_tv", "good_for_groups",
]

CATEGORICAL_FEATURES = [
    "noise_level",  # encoded as int
]

TARGET = "is_open"


# ── Cuisine extraction ────────────────────────────────────────────────────────

CUISINE_KEYWORDS = [
    "American", "Italian", "Chinese", "Japanese", "Mexican", "Thai",
    "Indian", "Korean", "Mediterranean", "Greek", "Vietnamese", "French",
    "Spanish", "Middle Eastern", "Pizza", "Burgers", "Seafood", "Sushi",
    "Barbecue", "Sandwiches", "Breakfast", "Desserts", "Vegan",
]

def extract_cuisine_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add one binary column per cuisine keyword."""
    for cuisine in CUISINE_KEYWORDS:
        col = f"cuisine_{cuisine.lower().replace(' ', '_')}"
        df[col] = df["categories"].str.contains(cuisine, case=False, na=False).astype(int)
    return df


# ── Noise level encoding ──────────────────────────────────────────────────────

NOISE_MAP = {"quiet": 0, "average": 1, "loud": 2, "very_loud": 3}

def encode_noise(val: str) -> int:
    if pd.isna(val):
        return -1
    return NOISE_MAP.get(str(val).strip().lower(), -1)


# ── Load & preprocess ─────────────────────────────────────────────────────────

def load_and_prepare(path: str) -> tuple[pd.DataFrame, list[str]]:
    print(f"Loading {path}…")
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    print(f"  {len(df):,} records loaded.")

    # Encode noise level
    df["noise_level"] = df["noise_level"].apply(encode_noise)

    # Cuisine flags
    df = extract_cuisine_flags(df)
    cuisine_cols = [f"cuisine_{c.lower().replace(' ', '_')}" for c in CUISINE_KEYWORDS]

    # Build feature list (only use columns that actually exist in the df)
    all_feats = NUMERIC_FEATURES + CATEGORICAL_FEATURES + cuisine_cols
    feature_cols = [f for f in all_feats if f in df.columns]

    # Coerce to numeric, fill missing with median
    for col in feature_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with no target
    df = df.dropna(subset=[TARGET])
    df[TARGET] = df[TARGET].astype(int)

    print(f"  Features used        : {len(feature_cols)}")
    print(f"  Open  (target=1)     : {df[TARGET].sum():,}")
    print(f"  Closed (target=0)    : {(df[TARGET]==0).sum():,}")
    print(f"  Class balance        : {df[TARGET].mean()*100:.1f}% open")

    # Fill medians per column
    medians = df[feature_cols].median()
    df[feature_cols] = df[feature_cols].fillna(medians)

    return df, feature_cols


# ── Train ─────────────────────────────────────────────────────────────────────

def train(df: pd.DataFrame, feature_cols: list[str]) -> tuple[xgb.XGBClassifier, dict]:
    X = df[feature_cols].values
    y = df[TARGET].values

    # Class imbalance weight
    neg = (y == 0).sum()
    pos = (y == 1).sum()
    scale_pos_weight = neg / pos if pos > 0 else 1.0

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        min_child_weight = 5,
        reg_alpha = 0.1,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="auc",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",  # fast for medium datasets
    )

    # ── Cross-validation ──────────────────────────────────────────────────────
    print("\nRunning 5-fold cross-validation…")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
    ap_scores  = cross_val_score(model, X, y, cv=cv, scoring="average_precision", n_jobs=-1)

    print(f"  ROC-AUC  : {auc_scores.mean():.4f} ± {auc_scores.std():.4f}")
    print(f"  Avg Prec : {ap_scores.mean():.4f} ± {ap_scores.std():.4f}")

    # ── Final fit on all data ─────────────────────────────────────────────────
    print("\nFitting final model on full dataset…")
    model.fit(X, y, verbose=False)

    # ── Feature importance ────────────────────────────────────────────────────
    importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
    importance_sorted = dict(sorted(importance.items(), key=lambda x: -x[1]))

    # ── Threshold tuning (maximize F1 on training data as proxy) ─────────────
    proba = model.predict_proba(X)[:, 1]
    best_thresh, best_f1 = 0.5, 0.0
    for t in np.arange(0.3, 0.8, 0.02):
        preds = (proba >= t).astype(int)
        tp = ((preds == 1) & (y == 1)).sum()
        fp = ((preds == 1) & (y == 0)).sum()
        fn = ((preds == 0) & (y == 1)).sum()
        prec = tp / (tp + fp + 1e-9)
        rec  = tp / (tp + fn + 1e-9)
        f1   = 2 * prec * rec / (prec + rec + 1e-9)
        if f1 > best_f1:
            best_f1, best_thresh = f1, t

    preds_final = (proba >= best_thresh).astype(int)
    cm = confusion_matrix(y, preds_final).tolist()
    report = classification_report(y, preds_final, output_dict=True)

    print(f"\n  Best threshold       : {best_thresh:.2f}")
    print(f"  Train F1             : {best_f1:.4f}")
    print(f"  Confusion matrix     : {cm}")

    # ── Top 20 most important features ───────────────────────────────────────
    top20 = list(importance_sorted.items())[:20]
    print("\n── Top 20 Feature Importances ──────────────────────────────────")
    for feat, imp in top20:
        bar = "█" * int(imp * 400)
        print(f"  {feat:<35} {imp:.4f}  {bar}")

    metrics = {
        "cv_roc_auc_mean":  round(float(auc_scores.mean()), 4),
        "cv_roc_auc_std":   round(float(auc_scores.std()), 4),
        "cv_avg_prec_mean": round(float(ap_scores.mean()), 4),
        "cv_avg_prec_std":  round(float(ap_scores.std()), 4),
        "best_threshold":   round(best_thresh, 4),
        "train_f1":         round(best_f1, 4),
        "confusion_matrix": cm,
        "classification_report": report,
    }

    return model, importance_sorted, metrics


# ── Save outputs ──────────────────────────────────────────────────────────────

def save_outputs(
    model: xgb.XGBClassifier,
    importance: dict,
    metrics: dict,
    feature_cols: list[str],
    out_dir: str,
):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Model
    model_path = out / "survival_model.json"
    model.save_model(str(model_path))
    print(f"\n  Saved model       → {model_path}")

    # Feature importance
    imp_path = out / "feature_importance.json"
    with open(imp_path, "w") as f:
        json.dump(importance, f, indent=2)
    print(f"  Saved importance  → {imp_path}")

    # Metadata (needed by the prediction API)
    meta = {
        "feature_cols": feature_cols,
        "metrics": metrics,
        "model_path": str(model_path.resolve()),
        "description": (
            "XGBoost classifier predicting restaurant survival (is_open=1). "
            "Input: per-business features from compute_review_features.py. "
            "Output: probability of staying open."
        ),
    }
    meta_path = out / "model_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Saved metadata    → {meta_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",   default="data/review_features.json", help="review_features.json path")
    parser.add_argument("--out_dir", default="models/",                   help="Directory to save model files")
    args = parser.parse_args()

    df, feature_cols = load_and_prepare(args.input)
    model, importance, metrics = train(df, feature_cols)
    save_outputs(model, importance, metrics, feature_cols, args.out_dir)

    print("\n✓ Done. Next step: add the /predict endpoint to main.py")
    print("  using the saved model + metadata to score new concepts.")


if __name__ == "__main__":
    main()