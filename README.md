# NJ Restaurant Market Gap Detector

Find underserved restaurant opportunities in New Jersey using Yelp data.

## Project Structure

```
restaurant-gap/
├── backend/          # FastAPI (Python)
│   ├── main.py       # All API endpoints
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # React
│   ├── src/
│   │   ├── App.js
│   │   ├── api.js          # All API calls
│   │   ├── hooks/useApi.js
│   │   ├── components/ui.js  # Shared components
│   │   └── pages/
│   │       ├── Opportunities.js  # "Where to open?"
│   │       ├── Search.js         # Concept search
│   │       └── Weakspots.js      # Weak competition finder
│   └── Dockerfile
├── data/
│   ├── gap_analysis.json         # Pre-computed gap scores (91 zips)
│   └── yelp_nj_restaurants.json  # Raw NJ restaurant data (3,341)
└── docker-compose.yml
```

## Setup

**Prerequisites:** Docker + Docker Compose

```bash
# 1. Make sure your data files are in /data:
#    data/gap_analysis.json
#    data/yelp_nj_restaurants.json

# 2. Start everything
docker-compose up --build

# Backend:  http://localhost:8000
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs   ← interactive Swagger UI
```

## API Endpoints

All endpoints return JSON. Test via `http://localhost:8000/docs`.

### `GET /opportunities`
**"Where should I open a [cuisine] restaurant?"**

| Param | Type | Description |
|---|---|---|
| `cuisine` | string | Target cuisine (e.g. `Japanese`) |
| `min_gap_score` | float | Minimum opportunity gap score |
| `min_market_size` | int | Minimum total reviews in zip |
| `max_risk` | string | `low` / `medium` / `high` |
| `sort` | string | `opportunity_score` / `market_size` / `stars` / `closure_risk` |
| `limit` | int | Max results (default 20) |

```bash
curl "http://localhost:8000/opportunities?cuisine=Japanese&max_risk=medium&sort=opportunity_score"
```

### `GET /opportunity/{zip}`
**"Is 08053 a good bet for my concept?"**

Full breakdown: cuisine gaps, attribute gaps, existing competition, plain-English signal summary, top local competitors.

```bash
curl "http://localhost:8000/opportunity/08053"
```

### `GET /search`
**"I want to open a mid-range BYOB Thai spot — where?"**

| Param | Type | Description |
|---|---|---|
| `cuisine` | string | Target cuisine |
| `byob` | bool | Requires BYOB gap in area |
| `delivery` | bool | Requires Delivery gap |
| `outdoor` | bool | Requires Outdoor Seating gap |
| `late_night` | bool | Requires Late Night gap |
| `kid_friendly` | bool | Requires Kid-Friendly gap |
| `max_price_tier` | float | 1=budget, 2=mid, 3=upscale |
| `max_risk` | string | Risk cap |
| `min_market_size` | int | Min reviews |

```bash
curl "http://localhost:8000/search?cuisine=Thai&byob=true&max_price_tier=2"
```

### `GET /weakspots`
**"Where is existing Italian failing — a better one would win."**

| Param | Type | Description |
|---|---|---|
| `cuisine` | string | Cuisine to evaluate |
| `min_closure_rate` | float | Min closure rate threshold (default 0.25) |
| `max_avg_stars` | float | Cap on existing quality (lower = weaker competition) |
| `min_existing` | int | Must have this many existing in category |

```bash
curl "http://localhost:8000/weakspots?cuisine=Italian&min_closure_rate=0.3&max_avg_stars=3.5"
```

### `GET /meta/cuisines`
Returns all 33 cuisine types and 7 attribute categories available for filtering.

---

## What the Analysis Is Doing

### Supply Matrix
For every zip code, we count: cuisine types present, attribute penetration rates (% of restaurants offering BYOB, delivery, etc.), price tier distribution.

### Spatial Demand Inference
Since we have no foot traffic data, latent demand is inferred using **geographic spillover**:
- Identify all zip codes within 20km radius
- Count how many restaurants of each cuisine exist in those neighbors
- If neighbors have 50 Thai restaurants but this zip has 0 → strong unmet demand signal

**Gap Score formula:**
```
gap_score = neighbor_cuisine_count / (local_count × local_avg_stars + 1)
```
The local quality in the denominator is intentional — a poorly-rated local competitor barely suppresses the score.

### Closure as a Risk + Opportunity Signal
`is_open = 0` restaurants are used two ways:
1. **Risk signal**: High closure rate in a zip = market has repeatedly failed there
2. **Opportunity signal**: High closure rate + specific cuisine + low quality = frustrated demand (Weakspots endpoint)

### Attribute Gap Detection
Cross-sectional: if 60% of restaurants within 20km offer BYOB but only 10% locally do, that's an actionable service differentiation opportunity — not just a data point.

### Composite Opportunity Score
```
opportunity_score = (top_gap_score × 0.6) + (log(total_reviews + 1) × 2) + (attr_gap_count × 5)
```
Balances gap magnitude, market size, and multi-dimensional opportunity.
