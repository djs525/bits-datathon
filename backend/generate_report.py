import json
import math
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
GAP_FILE = DATA_DIR / "gap_analysis.json"
OUTPUT_FILE = DATA_DIR / "recommendation_report.json"

def calculate_opportunity_score(z):
    # Expanded scoring formula
    top_gap = z["top_cuisine_gaps"][0]["gap_score"] if z["top_cuisine_gaps"] else 0
    market_size = math.log10(z["total_reviews"] + 1)
    stability = 1 - z["closure_rate"]
    attr_bonus = len(z["attr_gaps"]) * 2
    
    # Weighted Score (0-100)
    score = (top_gap * 4) + (market_size * 10) + (stability * 20) + attr_bonus
    return min(100, round(score, 1))

def generate_report():
    print("Loading gap analysis...")
    with open(GAP_FILE) as f:
        gaps = json.load(f)

    recommendations = []
    
    for z in gaps:
        score = calculate_opportunity_score(z)
        
        # Build recommendation object
        top_cuisine = z["top_cuisine_gaps"][0]["cuisine"] if z["top_cuisine_gaps"] else "General"
        
        rec = {
            "area_id": z["zip"],
            "area_name": z["city"],
            "opportunity_score": score,
            "primary_concept": top_cuisine,
            "evidence": {
                "demand_signal": f"High demand spillover for {top_cuisine} from neighbors.",
                "competitive_gap": f"Only {z['top_cuisine_gaps'][0]['local_count']} existing {top_cuisine} spots locally.",
                "market_size": f"{z['total_reviews']:,} total reviews in area.",
                "growth_potential": "High" if len(z["attr_gaps"]) > 2 else "Moderate"
            },
            "risk_assessment": {
                "closure_risk": "High" if z["closure_rate"] > 0.4 else "Medium" if z["closure_rate"] > 0.25 else "Low",
                "risk_factor": "Market saturated" if z["total_restaurants"] > 150 else "High churn" if z["closure_rate"] > 0.3 else "None significant"
            }
        }
        recommendations.append(rec)

    # Sort and take top 10
    recommendations.sort(key=lambda x: -x["opportunity_score"])
    top_10 = recommendations[:10]

    report = {
        "report_metadata": {
            "generated_at": "2026-02-28",
            "dataset_size": "4,205 NJ Food/Drink Businesses",
            "scope": "All NJ Food-related businesses (Expanded)"
        },
        "recommendations": top_10,
        "alternatives": [
            {
                "strategy": "High Traffic / High Risk",
                "zip": recommendations[10]["area_id"] if len(recommendations) > 10 else "N/A"
            },
            {
                "strategy": "Low Competition / Boutique",
                "zip": recommendations[15]["area_id"] if len(recommendations) > 15 else "N/A"
            }
        ]
    }

    print(f"Saving report to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    generate_report()
    print("Success.")
