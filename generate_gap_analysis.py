"""
generate_gap_analysis.py
========================
Generates data/gap_analysis.json from yelp_nj_restaurants.json.

This script computes per-zip-code gap scores used by the FastAPI backend:
  - Cuisine supply vs. neighbor demand (geographic spillover)
  - Attribute penetration rates vs. regional averages
  - Closure rates, star averages, market size

Usage
-----
    python generate_gap_analysis.py \
        --input  data/yelp_nj_restaurants.json \
        --output data/gap_analysis.json

Output schema (per zip)
-----------------------
{
  "zip": "08053",
  "city": "Marlton",
  "total_restaurants": 42,
  "open_restaurants": 31,
  "closure_rate": 0.262,
  "avg_stars": 3.54,
  "avg_reviews": 87.2,
  "total_reviews": 3662,
  "avg_price": 1.9,
  "num_neighbors": 8,
  "existing_cuisines": {"American": 12, "Italian": 5, ...},
  "top_cuisine_gaps": [
    {
      "cuisine": "Japanese",
      "gap_score": 18.4,
      "local_count": 1,
      "neighbor_demand": 24,
      "local_avg_stars": 3.5
    },
    ...
  ],
  "attr_gaps": [
    {
      "attribute": "BYOB",
      "local_rate": 0.08,
      "neighbor_avg": 0.35,
      "gap": 0.27
    },
    ...
  ]
}
"""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

NEIGHBOR_RADIUS_KM = 20
MIN_ZIP_RESTAURANTS = 3        # Skip zips too sparse to be meaningful
TOP_CUISINE_GAPS = 10          # How many cuisine gaps to store per zip
MIN_NEIGHBOR_DEMAND = 2        # Neighbor cuisine must appear at least N times to count
GAP_SCORE_MIN = 1.0            # Minimum gap score to include in top_cuisine_gaps

CUISINE_KEYWORDS = [
    "American", "Italian", "Chinese", "Japanese", "Mexican", "Thai",
    "Indian", "Korean", "Mediterranean", "Greek", "Vietnamese", "French",
    "Spanish", "Middle Eastern", "Pizza", "Burgers", "Seafood", "Sushi",
    "Barbecue", "Sandwiches", "Breakfast", "Desserts", "Vegan", "Halal",
    "Caribbean", "Soul Food", "Turkish", "Peruvian", "Brazilian", "Ethiopian",
    "Taiwanese", "Filipino",
]

ATTRIBUTE_MAP = {
    # display name → list of Yelp attribute keys to check
    "BYOB":             ["BYOB", "BYOBCorkage"],
    "Delivery":         ["RestaurantsDelivery"],
    "Outdoor Seating":  ["OutdoorSeating"],
    "Kid-Friendly":     ["GoodForKids"],
    "Late Night":       ["HappyHour"],           # proxy
    "Free WiFi":        ["WiFi"],
    "Reservations":     ["RestaurantsReservations"],
}


# ── Geo helpers ───────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two (lat, lon) points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Cuisine extraction ────────────────────────────────────────────────────────

def get_cuisines(categories: str) -> list[str]:
    """Return all matching cuisine keywords from a categories string."""
    if not categories:
        return []
    cats_lower = categories.lower()
    return [c for c in CUISINE_KEYWORDS if c.lower() in cats_lower]


# ── Attribute helpers ─────────────────────────────────────────────────────────

def attr_true(attrs: dict, keys: list[str]) -> bool:
    """Return True if any of the given attribute keys is truthy."""
    for k in keys:
        v = attrs.get(k)
        if v is None:
            continue
        sv = str(v).lower().strip().replace("u'", "").replace("'", "")
        if sv in ("true", "1", "yes", "free", "paid"):
            return True
        # WiFi special case: "free" or "paid" = has wifi
        if k == "WiFi" and sv not in ("no", "none", ""):
            return True
        if k == "BYOBCorkage" and sv not in ("no", "none", ""):
            return True
    return False


# ── Zip centroid ──────────────────────────────────────────────────────────────

def zip_centroid(restaurants: list[dict]) -> tuple[float, float] | None:
    """Compute median lat/lon for a zip code from its restaurants."""
    lats = [r["latitude"] for r in restaurants if r.get("latitude")]
    lons = [r["longitude"] for r in restaurants if r.get("longitude")]
    if not lats:
        return None
    return (
        sorted(lats)[len(lats) // 2],
        sorted(lons)[len(lons) // 2],
    )


# ── Main analysis ─────────────────────────────────────────────────────────────

def build_gap_analysis(restaurants: list[dict]) -> list[dict]:
    print(f"  {len(restaurants):,} restaurants loaded.")

    # ── Group by zip ──────────────────────────────────────────────────────────
    by_zip: dict[str, list] = defaultdict(list)
    for r in restaurants:
        z = str(r.get("postal_code", "")).strip()
        if z and len(z) == 5 and z.isdigit():
            by_zip[z].append(r)

    # Filter to valid NJ zips with enough data
    zip_codes = {z: rs for z, rs in by_zip.items() if len(rs) >= MIN_ZIP_RESTAURANTS}
    print(f"  {len(zip_codes)} zip codes with ≥{MIN_ZIP_RESTAURANTS} restaurants.")

    # ── Zip centroids ─────────────────────────────────────────────────────────
    centroids: dict[str, tuple[float, float]] = {}
    for z, rs in zip_codes.items():
        c = zip_centroid(rs)
        if c:
            centroids[z] = c

    # ── Per-zip stats ─────────────────────────────────────────────────────────
    zip_stats: dict[str, dict] = {}
    for z, rs in zip_codes.items():
        if z not in centroids:
            continue

        total = len(rs)
        open_count = sum(1 for r in rs if r.get("is_open", 0) == 1)
        closure_rate = round((total - open_count) / total, 4) if total else 0

        stars = [r["stars"] for r in rs if r.get("stars")]
        avg_stars = round(sum(stars) / len(stars), 3) if stars else 0

        reviews = [r.get("review_count", 0) or 0 for r in rs]
        total_reviews = sum(reviews)
        avg_reviews = round(total_reviews / total, 1) if total else 0

        prices = []
        for r in rs:
            attrs = r.get("attributes") or {}
            p = attrs.get("RestaurantsPriceRange2")
            try:
                prices.append(float(p))
            except (TypeError, ValueError):
                pass
        avg_price = round(sum(prices) / len(prices), 2) if prices else 2.0

        # City name (most common)
        cities = [r.get("city", "") for r in rs if r.get("city")]
        city = max(set(cities), key=cities.count) if cities else ""

        # Cuisine counts
        cuisine_counts: dict[str, int] = defaultdict(int)
        for r in rs:
            for c in get_cuisines(r.get("categories", "")):
                cuisine_counts[c] += 1

        zip_stats[z] = {
            "zip": z,
            "city": city,
            "total_restaurants": total,
            "open_restaurants": open_count,
            "closure_rate": closure_rate,
            "avg_stars": avg_stars,
            "avg_reviews": avg_reviews,
            "total_reviews": total_reviews,
            "avg_price": avg_price,
            "cuisine_counts": dict(cuisine_counts),
            "restaurants": rs,
        }

    print(f"  Computed stats for {len(zip_stats)} zip codes.")

    # ── Neighbor discovery ────────────────────────────────────────────────────
    zip_list = list(zip_stats.keys())
    neighbors: dict[str, list[str]] = defaultdict(list)

    for i, z1 in enumerate(zip_list):
        lat1, lon1 = centroids[z1]
        for z2 in zip_list[i + 1:]:
            lat2, lon2 = centroids[z2]
            if haversine_km(lat1, lon1, lat2, lon2) <= NEIGHBOR_RADIUS_KM:
                neighbors[z1].append(z2)
                neighbors[z2].append(z1)

    print(f"  Neighbor pairs found (radius={NEIGHBOR_RADIUS_KM}km).")

    # ── Attribute penetration ─────────────────────────────────────────────────
    # For each zip, compute local attr rates + neighbor avg rates

    def attr_rate(rs: list[dict], attr_name: str) -> float:
        keys = ATTRIBUTE_MAP[attr_name]
        hits = sum(1 for r in rs if attr_true(r.get("attributes") or {}, keys))
        return hits / len(rs) if rs else 0.0

    # ── Gap analysis per zip ──────────────────────────────────────────────────
    results = []
    for z, stats in zip_stats.items():
        nbrs = neighbors.get(z, [])
        neighbor_stats = [zip_stats[n] for n in nbrs if n in zip_stats]

        # ── Cuisine gaps ──────────────────────────────────────────────────────
        # For each cuisine type, compute gap score using all zips' cuisine counts
        local_cuisine = stats["cuisine_counts"]

        # Sum neighbor demand across all neighbor zips
        neighbor_demand: dict[str, int] = defaultdict(int)
        neighbor_stars: dict[str, list[float]] = defaultdict(list)

        for ns in neighbor_stats:
            for cuisine, cnt in ns["cuisine_counts"].items():
                neighbor_demand[cuisine] += cnt
            # Stars by cuisine in neighbors
            for r in ns["restaurants"]:
                for c in get_cuisines(r.get("categories", "")):
                    if r.get("stars"):
                        neighbor_stars[c].append(r["stars"])

        # Also get local stars per cuisine
        local_cuisine_stars: dict[str, list[float]] = defaultdict(list)
        for r in stats["restaurants"]:
            for c in get_cuisines(r.get("categories", "")):
                if r.get("stars"):
                    local_cuisine_stars[c].append(r["stars"])

        # All cuisines to evaluate = union of local + neighbor
        all_cuisines = set(local_cuisine.keys()) | set(neighbor_demand.keys())

        cuisine_gaps = []
        for cuisine in all_cuisines:
            nd = neighbor_demand.get(cuisine, 0)
            if nd < MIN_NEIGHBOR_DEMAND:
                continue  # Not enough regional demand to signal anything

            lc = local_cuisine.get(cuisine, 0)
            ls = local_cuisine_stars.get(cuisine, [])
            local_avg_stars = round(sum(ls) / len(ls), 3) if ls else 0.0

            # Gap formula: neighbor_demand / (local_count * local_avg_stars + 1)
            # Low quality local competitors barely suppress the score
            quality_suppression = lc * max(local_avg_stars, 1.0) + 1
            gap_score = round(nd / quality_suppression, 2)

            if gap_score < GAP_SCORE_MIN:
                continue

            cuisine_gaps.append({
                "cuisine": cuisine,
                "gap_score": gap_score,
                "local_count": lc,
                "neighbor_demand": nd,
                "local_avg_stars": local_avg_stars,
            })

        cuisine_gaps.sort(key=lambda x: -x["gap_score"])
        top_gaps = cuisine_gaps[:TOP_CUISINE_GAPS]

        # ── Attribute gaps ────────────────────────────────────────────────────
        local_rs = stats["restaurants"]
        attr_gaps = []

        for attr_name in ATTRIBUTE_MAP:
            local_rate = attr_rate(local_rs, attr_name)

            # Neighbor avg
            nbr_rates = [attr_rate(ns["restaurants"], attr_name) for ns in neighbor_stats]
            neighbor_avg = round(sum(nbr_rates) / len(nbr_rates), 4) if nbr_rates else 0.0

            gap = round(neighbor_avg - local_rate, 4)
            if gap > 0.05:  # Only report meaningful gaps
                attr_gaps.append({
                    "attribute": attr_name,
                    "local_rate": round(local_rate, 4),
                    "neighbor_avg": neighbor_avg,
                    "gap": gap,
                })

        attr_gaps.sort(key=lambda x: -x["gap"])

        # ── Existing cuisines (for the detail panel) ──────────────────────────
        existing_cuisines = {
            c: cnt for c, cnt in sorted(
                stats["cuisine_counts"].items(), key=lambda x: -x[1]
            )
        }

        results.append({
            "zip": z,
            "city": stats["city"],
            "total_restaurants": stats["total_restaurants"],
            "open_restaurants": stats["open_restaurants"],
            "closure_rate": stats["closure_rate"],
            "avg_stars": stats["avg_stars"],
            "avg_reviews": stats["avg_reviews"],
            "total_reviews": stats["total_reviews"],
            "avg_price": stats["avg_price"],
            "num_neighbors": len(nbrs),
            "existing_cuisines": existing_cuisines,
            "top_cuisine_gaps": top_gaps,
            "attr_gaps": attr_gaps,
        })

    results.sort(key=lambda x: x["zip"])
    return results


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate gap_analysis.json for the NJ Market Gap API.")
    parser.add_argument("--input",  default="data/yelp_nj_restaurants.json", help="Path to NJ restaurants JSON")
    parser.add_argument("--output", default="data/gap_analysis.json",        help="Output path")
    args = parser.parse_args()

    print(f"Loading {args.input}…")
    with open(args.input, encoding="utf-8") as f:
        content = f.read().strip()

    # Support both JSON array and newline-delimited JSON
    try:
        restaurants = json.loads(content)
    except json.JSONDecodeError:
        restaurants = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                try:
                    restaurants.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    print(f"\nRunning gap analysis…")
    results = build_gap_analysis(restaurants)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n── Summary ─────────────────────────────────────────────────────")
    print(f"  Zip codes analyzed   : {len(results)}")

    total_gaps = sum(len(z["top_cuisine_gaps"]) for z in results)
    total_attr = sum(len(z["attr_gaps"]) for z in results)
    avg_neighbors = round(sum(z["num_neighbors"] for z in results) / len(results), 1) if results else 0

    print(f"  Total cuisine gaps   : {total_gaps}")
    print(f"  Total attribute gaps : {total_attr}")
    print(f"  Avg neighbors/zip    : {avg_neighbors}")

    top5 = sorted(results, key=lambda z: -(z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0))[:5]
    print(f"\n  Top 5 opportunity zips:")
    for z in top5:
        tg = z["top_cuisine_gaps"][0] if z["top_cuisine_gaps"] else {}
        print(f"    {z['zip']} ({z['city']:<20}) top gap: {tg.get('cuisine','?'):<15} score={tg.get('gap_score',0)}")

    print(f"\n  ✓ Saved to {out_path.resolve()}")
    print("\nNext steps:")
    print("  1. python train_survival_model.py  (if you haven't already)")
    print("  2. uvicorn backend.main:app --reload")


if __name__ == "__main__":
    main()