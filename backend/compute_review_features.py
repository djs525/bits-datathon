"""
compute_review_features.py
==========================
Extracts rich per-business features from Yelp review data and merges them
with the NJ restaurant business data. The output is a single enriched JSON
file (`review_features.json`) ready for the XGBoost survival model.

Usage
-----
    python compute_review_features.py \
        --reviews  data/yelp_nj_reviews.json \
        --business data/yelp_nj_restaurants.json \
        --output   data/review_features.json

Dependencies
------------
    pip install pandas numpy vaderSentiment tqdm

What this produces (per business)
-----------------------------------
Temporal signals
    first_review_date       earliest review ISO date
    last_review_date        most recent review ISO date
    lifespan_days           days between first and last review
    review_velocity_30d     reviews in the last 30 days of activity
    review_velocity_90d     reviews in the last 90 days of activity
    reviews_per_month       avg reviews/month over full lifespan

Star trend
    star_slope              linear regression slope of stars over time
                            (positive = improving, negative = declining)
    stars_first_quartile    avg stars in earliest 25% of reviews
    stars_last_quartile     avg stars in most recent 25% of reviews
    star_delta              last_quartile - first_quartile

Distribution
    pct_1star               fraction of reviews that are 1-star
    pct_5star               fraction that are 5-star
    pct_negative            fraction ≤ 2 stars
    pct_positive            fraction ≥ 4 stars
    star_std                standard deviation of star ratings

Sentiment (VADER NLP)
    sentiment_mean          mean compound VADER score (-1 to +1)
    sentiment_std           std of compound scores
    sentiment_slope         linear trend of sentiment over time
    sentiment_last_quartile avg compound score in most recent 25% of reviews
    pct_very_positive       fraction with compound > 0.5
    pct_very_negative       fraction with compound < -0.5

Engagement
    useful_per_review       avg "useful" votes per review
    funny_per_review        avg "funny" votes per review
    cool_per_review         avg "cool" votes per review
    total_engagement        total useful+funny+cool
    pct_engaged_reviews     fraction of reviews with ≥1 engagement vote

Text richness
    avg_review_length       avg character count of review text
    median_review_length    median character count

Target label (from business data)
    is_open                 1 = still open, 0 = closed
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

# ── VADER sentiment ────────────────────────────────────────────────────────────
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
    _analyzer = SentimentIntensityAnalyzer()
except ImportError:
    VADER_AVAILABLE = False
    print(
        "⚠  vaderSentiment not installed — sentiment features will be skipped.\n"
        "   Install with:  pip install vaderSentiment",
        file=sys.stderr,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: str) -> list[dict]:
    """Handles both a JSON array and newline-delimited JSON."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    content = p.read_text(encoding="utf-8").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        records = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records


def parse_date(s: str) -> datetime:
    """Parse Yelp date strings like '2016-10-26 16:35:21'."""
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def linear_slope(values: list[float]) -> float:
    """Returns slope of OLS regression on (index, value) pairs. 0 if too few points."""
    n = len(values)
    if n < 3:
        return 0.0
    x = np.arange(n, dtype=float)
    y = np.array(values, dtype=float)
    x -= x.mean()
    denom = (x ** 2).sum()
    if denom == 0:
        return 0.0
    return float(np.dot(x, y) / denom)


def quartile_mean(values: list[float], q: str) -> float:
    """Mean of first or last 25% of a list (by position)."""
    n = len(values)
    if n == 0:
        return 0.0
    cut = max(1, n // 4)
    subset = values[:cut] if q == "first" else values[-cut:]
    return float(np.mean(subset))


# ── Core feature extraction ───────────────────────────────────────────────────

def extract_features_for_business(reviews: list[dict]) -> dict:
    """
    Given a list of review dicts for a single business (already sorted by date),
    return a flat feature dict.
    """
    if not reviews:
        return {}

    # Sort by date ascending
    dated = [(parse_date(r["date"]), r) for r in reviews]
    dated = [(d, r) for d, r in dated if d is not None]
    dated.sort(key=lambda x: x[0])

    if not dated:
        return {}

    dates = [d for d, _ in dated]
    revs = [r for _, r in dated]
    n = len(revs)

    stars_list = [float(r.get("stars", 0)) for r in revs]
    useful_list = [int(r.get("useful", 0)) for r in revs]
    funny_list = [int(r.get("funny", 0)) for r in revs]
    cool_list = [int(r.get("cool", 0)) for r in revs]
    texts = [r.get("text", "") or "" for r in revs]

    # ── Temporal ──────────────────────────────────────────────────────────────
    first_date = dates[0]
    last_date = dates[-1]
    lifespan_days = max((last_date - first_date).days, 1)
    lifespan_months = lifespan_days / 30.44

    # Velocity in last N days of the window
    def velocity(days: int) -> float:
        cutoff = last_date - pd.Timedelta(days=days)
        return sum(1 for d in dates if d >= cutoff)

    # ── Star features ─────────────────────────────────────────────────────────
    star_arr = np.array(stars_list)
    pct_1star = float((star_arr == 1).mean())
    pct_5star = float((star_arr == 5).mean())
    pct_negative = float((star_arr <= 2).mean())
    pct_positive = float((star_arr >= 4).mean())
    star_std = float(star_arr.std()) if n > 1 else 0.0
    star_slope = linear_slope(stars_list)
    stars_first_q = quartile_mean(stars_list, "first")
    stars_last_q = quartile_mean(stars_list, "last")
    star_delta = stars_last_q - stars_first_q

    # ── Sentiment ─────────────────────────────────────────────────────────────
    sentiment_feats = {}
    if VADER_AVAILABLE:
        scores = [_analyzer.polarity_scores(t)["compound"] for t in texts]
        s_arr = np.array(scores)
        sentiment_feats = {
            "sentiment_mean": float(s_arr.mean()),
            "sentiment_std": float(s_arr.std()) if n > 1 else 0.0,
            "sentiment_slope": linear_slope(scores),
            "sentiment_last_quartile": quartile_mean(scores, "last"),
            "pct_very_positive": float((s_arr > 0.5).mean()),
            "pct_very_negative": float((s_arr < -0.5).mean()),
        }
    else:
        sentiment_feats = {
            "sentiment_mean": None,
            "sentiment_std": None,
            "sentiment_slope": None,
            "sentiment_last_quartile": None,
            "pct_very_positive": None,
            "pct_very_negative": None,
        }

    # ── Engagement ────────────────────────────────────────────────────────────
    total_useful = sum(useful_list)
    total_funny = sum(funny_list)
    total_cool = sum(cool_list)
    total_engagement = total_useful + total_funny + total_cool
    engaged = sum(1 for u, f, c in zip(useful_list, funny_list, cool_list) if u + f + c > 0)

    # ── Text richness ─────────────────────────────────────────────────────────
    lengths = [len(t) for t in texts]
    avg_len = float(np.mean(lengths)) if lengths else 0.0
    med_len = float(np.median(lengths)) if lengths else 0.0

    return {
        # temporal
        "review_count_computed": n,
        "first_review_date": first_date.isoformat(),
        "last_review_date": last_date.isoformat(),
        "lifespan_days": lifespan_days,
        "review_velocity_30d": velocity(30),
        "review_velocity_90d": velocity(90),
        "reviews_per_month": round(n / lifespan_months, 4),
        # star distribution
        "pct_1star": round(pct_1star, 4),
        "pct_5star": round(pct_5star, 4),
        "pct_negative": round(pct_negative, 4),
        "pct_positive": round(pct_positive, 4),
        "star_std": round(star_std, 4),
        # star trend
        "star_slope": round(star_slope, 6),
        "stars_first_quartile": round(stars_first_q, 4),
        "stars_last_quartile": round(stars_last_q, 4),
        "star_delta": round(star_delta, 4),
        # sentiment
        **{k: (round(v, 4) if v is not None else None) for k, v in sentiment_feats.items()},
        # engagement
        "useful_per_review": round(total_useful / n, 4),
        "funny_per_review": round(total_funny / n, 4),
        "cool_per_review": round(total_cool / n, 4),
        "total_engagement": total_engagement,
        "pct_engaged_reviews": round(engaged / n, 4),
        # text
        "avg_review_length": round(avg_len, 1),
        "median_review_length": round(med_len, 1),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extract review features for NJ restaurants.")
    parser.add_argument("--reviews",  default="data/yelp_nj_reviews.json",      help="Path to NJ reviews JSON")
    parser.add_argument("--business", default="data/yelp_nj_restaurants.json",  help="Path to NJ restaurants JSON")
    parser.add_argument("--output",   default="data/review_features.json",       help="Output path")
    args = parser.parse_args()

    # ── Load ──────────────────────────────────────────────────────────────────
    print(f"Loading business data from {args.business}…")
    businesses = load_json(args.business)
    biz_lookup = {b["business_id"]: b for b in businesses}
    print(f"  {len(businesses):,} businesses loaded.")

    print(f"Loading reviews from {args.reviews}…")
    reviews = load_json(args.reviews)
    print(f"  {len(reviews):,} reviews loaded.")

    # ── Group reviews by business ─────────────────────────────────────────────
    print("Grouping reviews by business…")
    by_biz: dict[str, list] = defaultdict(list)
    for r in reviews:
        bid = r.get("business_id")
        if bid and bid in biz_lookup:
            by_biz[bid].append(r)

    print(f"  {len(by_biz):,} businesses have at least 1 review in this dataset.")

    # ── Extract features ──────────────────────────────────────────────────────
    print(f"\nExtracting features {'(with VADER sentiment)' if VADER_AVAILABLE else '(no sentiment — install vaderSentiment)'}…")
    results = []
    no_reviews = 0

    for biz in tqdm(businesses, desc="Processing", unit="biz"):
        bid = biz["business_id"]
        biz_reviews = by_biz.get(bid, [])

        if not biz_reviews:
            no_reviews += 1

        feats = extract_features_for_business(biz_reviews)

        # ── Business-level base features ──────────────────────────────────────
        attrs = biz.get("attributes") or {}

        def attr_bool(key: str) -> int | None:
            v = attrs.get(key)
            if v is None:
                return None
            return 1 if str(v).lower() in ("true", "1", "yes") else 0

        price_raw = attrs.get("RestaurantsPriceRange2")
        try:
            price_tier = float(price_raw) if price_raw else None
        except (ValueError, TypeError):
            price_tier = None

        record = {
            # identifiers
            "business_id": bid,
            "name": biz.get("name"),
            "city": biz.get("city"),
            "postal_code": biz.get("postal_code"),
            "categories": biz.get("categories"),
            "latitude": biz.get("latitude"),
            "longitude": biz.get("longitude"),
            # base business features
            "stars_yelp": biz.get("stars"),
            "review_count_yelp": biz.get("review_count"),
            "price_tier": price_tier,
            "has_delivery": attr_bool("RestaurantsDelivery"),
            "has_takeout": attr_bool("RestaurantsTakeOut"),
            "has_outdoor_seating": attr_bool("OutdoorSeating"),
            "good_for_kids": attr_bool("GoodForKids"),
            "has_reservations": attr_bool("RestaurantsReservations"),
            "has_wifi": 1 if str(attrs.get("WiFi", "")).lower() not in ("u'no'", "no", "none", "") else 0,
            "has_alcohol": 1 if "full_bar" in str(attrs.get("Alcohol", "")).lower() or "beer_and_wine" in str(attrs.get("Alcohol", "")).lower() else 0,
            "has_tv": attr_bool("HasTV"),
            "good_for_groups": attr_bool("RestaurantsGoodForGroups"),
            "noise_level": str(attrs.get("NoiseLevel", "")).replace("u'", "").replace("'", "").strip(),
            # target
            "is_open": int(biz.get("is_open", 0)),
            # computed review features
            **feats,
        }
        results.append(record)

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f"\nSaving {len(results):,} records to {args.output}…")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    # ── Summary ───────────────────────────────────────────────────────────────
    open_ct = sum(1 for r in results if r["is_open"] == 1)
    closed_ct = sum(1 for r in results if r["is_open"] == 0)
    with_reviews = len(results) - no_reviews
    feats_per_record = len([k for k in results[0] if k not in ("business_id", "name", "city", "postal_code", "categories", "latitude", "longitude")])

    print("\n── Summary ─────────────────────────────────────────────────────")
    print(f"  Total records        : {len(results):,}")
    print(f"  With review data     : {with_reviews:,}  ({round(with_reviews/len(results)*100)}%)")
    print(f"  Without reviews      : {no_reviews:,}")
    print(f"  Open businesses      : {open_ct:,}")
    print(f"  Closed businesses    : {closed_ct:,}  (closure rate: {closed_ct/len(results)*100:.1f}%)")
    print(f"  Features per record  : {feats_per_record}")
    print(f"  VADER sentiment      : {'✓ included' if VADER_AVAILABLE else '✗ skipped (not installed)'}")
    print(f"\n  Output: {out_path.resolve()}")
    print("\nNext step: run train_survival_model.py on this output file.")


if __name__ == "__main__":
    main()