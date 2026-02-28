from fastapi import FastAPI, Query
from typing import List, Optional
import json
import pandas as pd
from datetime import datetime

app = FastAPI(title="SlackDigest API")

# Load data
DATA_PATH = 'triaged_messages.json'

def load_data():
    with open(DATA_PATH, 'r') as f:
        return json.load(f)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to SlackDigest API",
        "endpoints": {
            "digest": "/digest",
            "stats": "/stats",
            "docs": "/docs"
        }
    }

@app.get("/digest")
def get_digest(category: Optional[str] = None):
    data = load_data()
    if category:
        data = [m for m in data if m['category'].lower() == category.lower()]
    # Sort by priority desc
    data.sort(key=lambda x: x['priority'], reverse=True)
    return data

@app.get("/stats")
def get_stats():
    data = load_data()
    df = pd.DataFrame(data)
    
    # 1. Category Distribution
    cat_dist = df['category'].value_counts().to_dict()
    
    # 2. Volume over time (grouped by day)
    # The Enron dates are complex, we use utc=True to handle mixed offsets
    df['date'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
    
    # Drop rows where date couldn't be parsed to avoid Index errors during resample
    df_vol = df.dropna(subset=['date'])
    
    volume_over_time = df_vol.set_index('date').resample('D').size().rename("count").reset_index()
    volume_over_time['date'] = volume_over_time['date'].dt.strftime('%Y-%m-%d')
    volume_over_time = volume_over_time.to_dict(orient='records')
    
    # 3. Top Priority Items
    top_items = df.sort_values(by='priority', ascending=False).head(10)[['user', 'category', 'priority', 'channel']].to_dict(orient='records')
    
    # 4. User Activity
    user_activity = df['user'].value_counts().head(10).to_dict()
    
    # 5. Channel Stats
    channel_stats = df.groupby('channel')['category'].value_counts().unstack(fill_value=0).to_dict(orient='index')
    
    return {
        "category_distribution": cat_dist,
        "volume_over_time": volume_over_time,
        "top_priority_items": top_items,
        "user_activity": user_activity,
        "channel_stats": channel_stats
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
