# NJ Restaurant Market Gap Detector

An AI-powered decision support platform for entrepreneurs to identify underserved restaurant opportunities in New Jersey. Using Yelp dataset insights, the platform helps users find the perfect location, cuisine type, and service attributes to maximize their business survival probability.

## 🚀 Key Features

- **Market Gap Analysis**: Visualizes supply-demand imbalances across 91 New Jersey zip codes.
- **Personalized Recommendations**: Dynamic ranking of areas based on specific cuisine interests and risk tolerance.
- **Survival Predictor**: An XGBoost-powered model that predicts the survival probability of a new restaurant concept with SHAP explanations.
- **Service Gaps**: Identifies missing attributes (e.g., BYOB, Outdoor Seating, Delivery) that can differentiate a new business.

## 🛠 Tech Stack

- **Backend**: Python, FastAPI, XGBoost, SHAP, Pandas.
- **Frontend**: React, Vanilla CSS (Modern Premium UI).
- **Data**: Yelp Open Dataset (NJ subset).
- **Deployment**: Docker, Docker Compose.

---

## 🚦 Getting Started

### Prerequisites
- **Docker** and **Docker Compose**
- **Python 3.11+** (for local data processing)

### 1. Initial Setup
Clone the repository and create your local environment:
```bash
git clone https://github.com/itamaramsalem/bits-datathon.git
cd bits-datathon

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Data Preparation
The API requires pre-processed data which is generated from the raw Yelp dataset. Run the following:
```bash
# Generate the gap analysis JSON (Required for API)
python3 generate_gap_analysis.py

# Train the Survival Prediction model (Required for /predict)
python3 backend/train_survival_model.py
```

### 3. Running with Docker
The easiest way to start both the frontend and backend is via Docker Compose:
```bash
docker-compose up --build
```
- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📂 Project Structure

```text
.
├── backend/                # FastAPI application & ML Training
│   ├── main.py             # API Entry point
│   ├── train_survival_model.py
│   └── requirements.txt
├── frontend/               # React application
│   ├── src/
│   │   ├── App.js
│   │   └── pages/          # Market Gaps, Recommendations, Predictor
├── data/                   # JSON data (generated)
├── models/                 # Saved XGBoost models & metadata
└── docker-compose.yml      # Orchestration
```

## 🧪 Development

### Running Backend Manually
```bash
cd backend
uvicorn main:app --reload
```

### Running Frontend Manually
```bash
cd frontend
npm install
npm start
```

## 📄 License
This project is part of the BITS Datathon 2024. See `CONTRIBUTING.md` for development workflows.
