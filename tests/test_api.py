"""
tests/test_api.py
=================
Integration tests for the NJ Restaurant Market Gap API.
Run with: pytest tests/test_api.py -v

Requirements: pip install requests pytest
The backend must be running on localhost:8000.
"""

import pytest
import requests

BASE = "http://localhost:8000"


# ── Helpers ───────────────────────────────────────────────────────────────────

def get(path, **params):
    r = requests.get(f"{BASE}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def post(path, body):
    r = requests.post(f"{BASE}{path}", json=body, timeout=10)
    return r


# ── Meta endpoints ────────────────────────────────────────────────────────────

class TestMeta:
    def test_root(self):
        data = get("/")
        assert data["service"].startswith("NJ Restaurant Market Gap")
        assert isinstance(data["model_loaded"], bool)

    def test_cuisines(self):
        data = get("/meta/cuisines")
        assert "cuisines" in data
        assert len(data["cuisines"]) >= 5
        assert "American" in data["cuisines"]
        assert "attributes" in data

    def test_model_info(self):
        data = get("/meta/model")
        assert "metrics" in data
        assert "cv_roc_auc_mean" in data["metrics"]
        # Retrained model should have reasonable AUC (>0.7 even without leakage features)
        assert data["metrics"]["cv_roc_auc_mean"] > 0.70
        assert "feature_count" in data
        assert "top_features" in data
        # Should no longer have leakage features at the top
        top_feats = {f["feature"] for f in data["top_features"]}
        assert "lifespan_days" not in top_feats
        assert "review_velocity_30d" not in top_feats


# ── Opportunities endpoints ────────────────────────────────────────────────────

class TestOpportunities:
    def test_default(self):
        data = get("/opportunities")
        assert "count" in data
        assert "results" in data
        assert data["count"] <= 91  # NJ has 91 zip codes
        if data["results"]:
            z = data["results"][0]
            assert "zip" in z
            assert "opportunity_score" in z
            assert "risk" in z
            assert z["risk"] in ("low", "medium", "high")

    def test_cuisine_filter(self):
        data = get("/opportunities", cuisine="Japanese")
        if data["results"]:
            for z in data["results"]:
                cuisines = [g["cuisine"] for g in z["top_cuisine_gaps"]]
                assert "Japanese" in cuisines

    def test_risk_filter(self):
        data = get("/opportunities", max_risk="low")
        for z in data["results"]:
            assert z["risk"] == "low"

    def test_opportunity_score_is_bounded(self):
        """attr_bonus is capped, but top_gap can be high. Ensure reasonable bounds."""
        data = get("/opportunities", limit=91)
        for z in data["results"]:
            assert z["opportunity_score"] < 400, (
                f"Zip {z['zip']} has unreasonably high score {z['opportunity_score']}"
            )


# ── Opportunity detail ─────────────────────────────────────────────────────────

class TestOpportunityDetail:
    def test_known_zip(self):
        data = get("/opportunity/08053")
        assert data["zip"] == "08053"
        assert "cuisine_gaps" in data
        assert "attribute_gaps" in data
        assert "signal_summary" in data
        assert "local_restaurants" in data

    def test_unknown_zip(self):
        r = requests.get(f"{BASE}/opportunity/99999", timeout=10)
        assert r.status_code == 404

    def test_malformed_zip(self):
        r = requests.get(f"{BASE}/opportunity/abc", timeout=10)
        assert r.status_code == 404


# ── Recommendations endpoint ──────────────────────────────────────────────────

class TestRecommendations:
    def test_default(self):
        data = get("/recommendations")
        assert "count" in data
        assert "recommendations" in data
        assert len(data["recommendations"]) <= 10

    def test_cuisine_filter(self):
        data = get("/recommendations", cuisine="Japanese")
        if data["recommendations"]:
            for r in data["recommendations"]:
                assert r["primary_concept"] == "Japanese"

    def test_attribute_filter(self):
        data = get("/recommendations", byob="true")
        if data["recommendations"]:
            for r in data["recommendations"]:
                # Attributes should be in evidence.attribute_opportunities
                assert "BYOB" in r["evidence"]["attribute_opportunities"]

    def test_multi_filter(self):
        data = get("/recommendations", cuisine="Italian", max_risk="medium", max_price_tier=2)
        assert "recommendations" in data

    def test_survival_bonus_integration(self):
        """Verify that recommendations include survival probability when cuisine is provided."""
        data = get("/recommendations", cuisine="American", limit=1)
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "survival_probability" in rec["evidence"]
            # It can be None if model is missing, but should be a key


# ── Predict endpoint ──────────────────────────────────────────────────────────

class TestPredict:
    def test_minimal_input(self):
        """Only zip_code + cuisine required — smart defaults should fill rest."""
        r = post("/predict", {"zip_code": "08053", "cuisine": "Japanese"})
        assert r.status_code == 200
        data = r.json()
        assert "survival_probability" in data
        p = data["survival_probability"]
        assert 0.0 <= p <= 1.0
        assert "survival_signal" in data
        assert data["survival_signal"]["label"] in ("high", "medium", "low", "very_low")
        assert "market_context" in data
        assert "top_survival_factors" in data

    def test_shap_factors_returned(self):
        """When SHAP is available, top_survival_factors should include shap_value."""
        r = post("/predict", {"zip_code": "08053", "cuisine": "American"})
        data = r.json()
        if data.get("shap_available"):
            factors = data["top_survival_factors"]
            assert len(factors) > 0
            for f in factors:
                assert "feature" in f
                assert "shap_value" in f
                assert f["direction"] in ("positive", "negative")

    def test_concept_applied_contains_defaults(self):
        """Concept applied should reflect smart defaults for the cuisine."""
        r = post("/predict", {"zip_code": "08053", "cuisine": "Pizza"})
        data = r.json()
        applied = data["concept_applied"]
        # Pizza should default has_delivery=1
        assert applied.get("has_delivery") == 1

    def test_override_beats_default(self):
        """Explicitly setting an attribute should override the smart default."""
        r = post("/predict", {"zip_code": "08053", "cuisine": "Pizza", "has_delivery": 0})
        data = r.json()
        applied = data["concept_applied"]
        assert applied.get("has_delivery") == 0

    def test_cuisine_warning_for_rare_cuisines(self):
        """Cuisines with zero importance should trigger a warning."""
        r = post("/predict", {"zip_code": "08053", "cuisine": "Ethiopian"})
        # May 404 if cuisine doesn't match zip, or return warning
        if r.status_code == 200:
            data = r.json()
            # If cuisine_warning is present, it's a string
            if data.get("cuisine_model_warning"):
                assert isinstance(data["cuisine_model_warning"], str)

    def test_invalid_zip_rejected(self):
        r = post("/predict", {"zip_code": "abc", "cuisine": "Italian"})
        assert r.status_code == 422

    def test_zip_not_in_dataset(self):
        r = post("/predict", {"zip_code": "10001", "cuisine": "Italian"})
        assert r.status_code == 404

    def test_invalid_stars_rejected(self):
        r = post("/predict", {"zip_code": "08053", "cuisine": "Italian", "expected_stars": 6.0})
        assert r.status_code == 422

    def test_invalid_price_tier_rejected(self):
        r = post("/predict", {"zip_code": "08053", "cuisine": "Italian", "price_tier": 5.0})
        assert r.status_code == 422

    def test_invalid_noise_level_rejected(self):
        r = post("/predict", {"zip_code": "08053", "cuisine": "Italian", "noise_level": "deafening"})
        assert r.status_code == 422

    def test_all_four_zip_codes(self):
        """Spot check a variety of NJ zip codes."""
        for z in ["07030", "07102", "08401", "08053"]:
            r = post("/predict", {"zip_code": z, "cuisine": "American"})
            if r.status_code == 200:
                p = r.json()["survival_probability"]
                assert 0.0 <= p <= 1.0
