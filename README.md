# GSD.AI (Garden State Detector) 📍🥪

**An AI-Powered Market Intelligence & Survival Predictor for New Jersey Restaurants**

GSD.AI is a full-stack, AI-driven platform that revolutionizes how culinary entrepreneurs find opportunities and assess risk. By analyzing thousands of historical Yelp reviews and restaurant firmographic data across New Jersey, GSD.AI calculates real-time **market gaps** and predicts the **survival probability** of new restaurant concepts before you even sign a lease.

---

## 🌟 Key Features

1. **Market Gap Discovery (`Opportunities`)**
   - Interactive map powered by Carto and Leaflet.
   - Highlights hyper-local "Cuisine Gaps" where neighbor demand outpaces existing supply.
   - Dynamic real-time Opportunity Scoring (1-100) based on local competition and historic closure rates.
   
2. **AI Recommendation Engine (`Recommendations`)**
   - You input a concept (e.g., "Japanese, Mid-tier pricing, Kid Friendly").
   - The algorithmic engine sorts all NJ Zip Codes to find your perfect match.
   - Features rigid risk-tolerance filtering to block zip codes historically prone to fast closures.

3. **Survival Predictor (`Predict`)**
   - An integrated **XGBoost Machine Learning survival model**.
   - Input a zip code + your concept attributes (Delivery, Outdoor Seating, Alcohol, etc.).
   - Returns a percentage probability that the business will survive its first 3 years.
   - Includes full **SHAP (SHapley Additive exPlanations) integration**, breaking down *exactly* why the AI gave you that score (e.g., "Having no delivery in this specific zip code hurts your chances by -4.2%").

4. **Apple-Esque Ultra-Premium UI**
   - Minimalist "Airbnb meets iOS" design language.
   - Features GPU-accelerated fluid bounces, 200% saturation glassmorphism, inner-refraction borders, and sleek data visualizations.

---

## 🏗️ Architecture

- **Frontend:** React.js, Context API, CSS Variables (Custom Design System), `react-leaflet` for mapping.
- **Backend:** Python, FastAPI, Pandas, NumPy.
- **Machine Learning:** XGBoost (Survival/Risk Model), SHAP (Model Interpretability), VADER (Sentiment Analysis of Review Text).
- **Data:** Yelp Open Dataset (Filtered to NJ).

---

## 🚀 Getting Started

To run this project locally, you will need two terminal windows—one for the Python backend and one for the React frontend.

### 1. Start the Backend (FastAPI + ML Model)

Navigate to the `backend` directory, install the Python requirements, and spin up the server.

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the API server on port 8000
uvicorn main:app --reload
```

*Note: The backend relies on a trained XGBoost model and pre-computed gap data. If you are starting fresh, ensure the `trained_model` folder and `gap_analysis.json` exist, or run the preprocessing/training scripts included in the backend.*

### 2. Start the Frontend (React)

Open a new terminal, navigate to the `frontend` folder, install Node dependencies, and start the development server.

```bash
cd frontend
npm install

# Start the React app on port 3000
npm start
```

Once both servers are running, open your browser to [http://localhost:3000](http://localhost:3000) and explore the platform!

---

## 💡 How It Works (The Data Science)

- **The Dataset:** We aggregated Yelp reviews spanning back years. We identified closed vs. open businesses to formulate our ground truth for survival.
- **NLP / Sentiment Pipeline:** VADER sentiment analysis processes bulk review text to determine the "mood" of specific neighborhoods, which acts as a powerful feature for our XGBoost model.
- **Demand Proxy Engine:** `Gap Scores` aren't just based on a lack of restaurants. They are calculated dynamically by looking at the density/review-velocity of *neighboring* zip codes to establish a baseline "Proven Demand Ceiling", and then subtracting local competitors.
- **SHAP Explanation:** Because ML models are often "black boxes", we run a SHAP TreeExplainer in real-time inside the FastAPI backend. This allows the UI to display positive and negative transparent feature weights so entrepreneurs know exactly what operational choices to tweak.
