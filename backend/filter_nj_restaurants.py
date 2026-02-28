import json
import pandas as pd
from pathlib import Path

# ── Load ──────────────────────────────────────────────────────────────────────
def load_json(path):
    """Handles both JSON array and newline-delimited JSON."""
    with open(path) as f:
        content = f.read().strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        records = []
        for line in content.split("\n"):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return records


# ── Filter ────────────────────────────────────────────────────────────────────
def filter_restaurants(records):
    """Keep only food-service and nightlife businesses."""
    keywords = {
        'Restaurants', 'Food', 'Bars', 'Nightlife', 'Sandwiches', 'Pizza', 
        'Italian', 'Mexican', 'Chinese', 'Japanese', 'Breakfast & Brunch', 
        'Bakery', 'Desserts', 'Ice Cream & Frozen Yogurt', 'Coffee & Tea', 
        'Delis', 'Seafood', 'Steakhouses', 'Diners', 'Specialty Food', 'Fast Food'
    }
    filtered = []
    for r in records:
        cats = set((r.get("categories") or "").split(", "))
        if keywords & cats:
            filtered.append(r)
    return filtered


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    DATA_DIR = Path(__file__).parent.parent / "data"
    INPUT_PATH  = DATA_DIR / "yelp_nj_business.json"
    OUTPUT_JSON = DATA_DIR / "yelp_nj_restaurants.json"
    OUTPUT_CSV  = DATA_DIR / "yelp_nj_restaurants.csv"

    print(f"Loading data from {INPUT_PATH}...")
    records = load_json(INPUT_PATH)
    print(f"  Total NJ businesses : {len(records):,}")

    restaurants = filter_restaurants(records)
    print(f"  Restaurants found   : {len(restaurants):,}")

    # ── Save JSON ──────────────────────────────────────────────────────────────
    with open(OUTPUT_JSON, "w") as f:
        json.dump(restaurants, f, indent=2)
    print(f"  Saved → {OUTPUT_JSON}")

    # ── Save CSV ───────────────────────────────────────────────────────────────
    df = pd.DataFrame(restaurants)

    # Flatten hours dict into readable string
    def fmt_hours(h):
        if not isinstance(h, dict):
            return None
        return " | ".join(f"{d}: {v}" for d, v in sorted(h.items()))

    df["hours_fmt"] = df["hours"].apply(fmt_hours)

    # Drop the raw nested columns for a clean CSV
    csv_cols = [
        "business_id", "name", "address", "city", "postal_code",
        "state", "latitude", "longitude",
        "categories", "stars", "review_count", "is_open", "hours_fmt"
    ]
    df[csv_cols].to_csv(OUTPUT_CSV, index=False)
    print(f"  Saved → {OUTPUT_CSV}")

    # ── Quick summary ──────────────────────────────────────────────────────────
    print("\n── Summary ────────────────────────────────────────────────────")
    print(f"  Open restaurants    : {df['is_open'].sum():,}")
    print(f"  Closed restaurants  : {(df['is_open'] == 0).sum():,}")
    print(f"  Avg star rating     : {df['stars'].mean():.2f}")
    print(f"  Avg review count    : {df['review_count'].mean():.1f}")
    print(f"\n  Top 10 zip codes by restaurant count:")
    print(df["postal_code"].value_counts().head(10).to_string())

    # ── Save zip-level summary ─────────────────────────────────────────────────
    zip_summary = (
        df.groupby("postal_code")
        .agg(
            city=("city", lambda x: x.mode()[0]),          # most common city name in zip
            restaurant_count=("business_id", "count"),
            open_count=("is_open", "sum"),
            closed_count=("is_open", lambda x: (x == 0).sum()),
            avg_stars=("stars", "mean"),
            avg_reviews=("review_count", "mean"),
            total_reviews=("review_count", "sum"),
        )
        .round(2)
        .sort_values("restaurant_count", ascending=False)
        .reset_index()
    )
    zip_summary.to_csv("yelp_nj_restaurants_by_zip.csv", index=False)
    print(f"\n  Saved → yelp_nj_restaurants_by_zip.csv")
    print(f"  Unique zip codes    : {len(zip_summary):,}")
    print(zip_summary.head(10).to_string(index=False))