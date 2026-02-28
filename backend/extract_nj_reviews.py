import json
import os
import sys

def main():
    business_file = "yelp_nj_restaurants.json"  
    review_file = "yelp_academic_dataset_review.json"
    output_file = "yelp_nj_reviews.json"

    if not os.path.exists(business_file):
        print(f"Error: {business_file} not found. Run the business extraction first.")
        return

    print(f"Loading NJ business IDs from {business_file}...")
    with open(business_file, "r", encoding="utf-8") as f:
        nj_businesses = json.load(f)
    
    nj_business_ids = {b["business_id"] for b in nj_businesses}
    print(f"Found {len(nj_business_ids)} NJ businesses.")

    print(f"Filtering {review_file} for NJ reviews... (Streaming 5GB file)")
    count = 0
    matches = []
    
    # Process line-by-line to save memory
    with open(review_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                review = json.loads(line)
                if review.get("business_id") in nj_business_ids:
                    matches.append(review)
                    count += 1
                    if count % 1000 == 0:
                        print(f"Found {count} reviews so far...", end="\r")
            except json.JSONDecodeError:
                continue

    print(f"\nDone! Found {count} NJ reviews.")
    
    print(f"Saving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, sort_keys=True)
    
    print("Success.")

if __name__ == "__main__":
    main()
