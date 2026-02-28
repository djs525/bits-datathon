import json
import math
from pathlib import Path
from collections import defaultdict

# ── Configuration ─────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
INPUT_FILE = DATA_DIR / "yelp_nj_restaurants.json"
OUTPUT_FILE = DATA_DIR / "gap_analysis.json"

CUISINES = [
    "American", "Italian", "Chinese", "Japanese", "Mexican", "Thai",
    "Indian", "Korean", "Mediterranean", "Greek", "Vietnamese", "French",
    "Spanish", "Middle Eastern", "Pizza", "Burgers", "Seafood", "Sushi",
    "Barbecue", "Sandwiches", "Breakfast", "Desserts", "Vegan", "Steakhouses",
    "Diners", "Bakeries", "Coffee & Tea", "Bars", "Pubs", "Wine Bars"
]

ATTRIBUTES = [
    "BYOB", "HasTV", "OutdoorSeating", "RestaurantsDelivery", 
    "GoodForKids", "Caters", "RestaurantsReservations"
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_dist(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ── Main ──────────────────────────────────────────────────────────────────────

print("Loading expanded dataset...")
with open(INPUT_FILE) as f:
    restaurants = json.load(f)

print(f"  Total records: {len(restaurants)}")

# 1. Group by Zip
zip_groups = defaultdict(list)
for r in restaurants:
    zip_groups[r.get("postal_code")].append(r)

zips = sorted(list(zip_groups.keys()))
zip_coords = {}
for z in zips:
    lats = [r["latitude"] for r in zip_groups[z] if r.get("latitude")]
    lons = [r["longitude"] for r in zip_groups[z] if r.get("longitude")]
    if lats and lons:
        zip_coords[z] = (sum(lats)/len(lats), sum(lons)/len(lons))

# 2. Re-compute Gaps per Zip
gap_analysis = []

for z in zips:
    local_r = zip_groups[z]
    if not local_r: continue
    
    city = local_r[0].get("city")
    coords = zip_coords.get(z)
    if not coords: continue

    # Find neighbors within 15km
    neighbors = [nz for nz, nc in zip_coords.items() if nz != z and get_dist(coords[0], coords[1], nc[0], nc[1]) <= 15]
    neighbor_r = []
    for nz in neighbors:
        neighbor_r.extend(zip_groups[nz])

    # Cuisine Analysis
    cuisine_gaps = []
    local_cats = defaultdict(int)
    for r in local_r:
        if not r.get("is_open"): continue
        cats = r.get("categories") or ""
        for c in CUISINES:
            if c in cats: local_cats[c] += 1
            
    neighbor_cats = defaultdict(int)
    for r in neighbor_r:
        if not r.get("is_open"): continue
        cats = r.get("categories") or ""
        for c in CUISINES:
            if c in cats: neighbor_cats[c] += 1

    for c in CUISINES:
        local_count = local_cats[c]
        neighbor_demand = neighbor_cats[c]
        # Gap formula: demand spillover weighted by lack of local supply
        gap_score = neighbor_demand / (local_count * 1.5 + 1)
        if gap_score > 0.5:
            cuisine_gaps.append({
                "cuisine": c,
                "gap_score": round(gap_score, 2),
                "local_count": local_count,
                "neighbor_demand": neighbor_demand
            })
    
    cuisine_gaps.sort(key=lambda x: -x["gap_score"])

    # Attribute Analysis
    attr_gaps = []
    for attr in ATTRIBUTES:
        local_with = sum(1 for r in local_r if r.get("attributes") and r["attributes"].get(attr) == "True")
        local_rate = local_with / len(local_r)
        
        neigh_with = sum(1 for r in neighbor_r if r.get("attributes") and r["attributes"].get(attr) == "True")
        neigh_rate = neigh_with / len(neighbor_r) if neighbor_r else 0
        
        if neigh_rate > local_rate + 0.1:
            attr_gaps.append({
                "attribute": attr,
                "gap": round(neigh_rate - local_rate, 3),
                "local_rate": round(local_rate, 3),
                "neighbor_avg": round(neigh_rate, 3)
            })

    # Stats
    record = {
        "zip": z,
        "city": city,
        "total_restaurants": len(local_r),
        "open_restaurants": sum(1 for r in local_r if r.get("is_open")),
        "closure_rate": round(sum(1 for r in local_r if not r.get("is_open")) / len(local_r), 4),
        "avg_stars": round(sum(r["stars"] for r in local_r) / len(local_r), 2),
        "total_reviews": sum(r["review_count"] for r in local_r),
        "avg_reviews": round(sum(r["review_count"] for r in local_r) / len(local_r), 1),
        "avg_price": round(sum(int(r["attributes"].get("RestaurantsPriceRange2", 2)) for r in local_r if r.get("attributes") and r["attributes"].get("RestaurantsPriceRange2", "2").isdigit()) / len(local_r), 2),
        "top_cuisine_gaps": cuisine_gaps[:5],
        "attr_gaps": attr_gaps,
        "num_neighbors": len(neighbors),
        "existing_cuisines": dict(local_cats)
    }
    gap_analysis.append(record)

print(f"Saving gap analysis to {OUTPUT_FILE}...")
with open(OUTPUT_FILE, "w") as f:
    json.dump(gap_analysis, f, indent=2)

print("Done.")
