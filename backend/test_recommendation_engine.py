import json
import unittest
from pathlib import Path

# Paths
DATA_DIR = Path("/Users/anujpatil/Desktop/datathon/bits-datathon/data")
REPORT_FILE = DATA_DIR / "recommendation_report.json"

class TestRecommendationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not REPORT_FILE.exists():
            raise FileNotFoundError(f"Recommendation report not found at {REPORT_FILE}")
        with open(REPORT_FILE, "r") as f:
            cls.report = json.load(f)

    def test_report_structure(self):
        """Verify the report has the required top-level fields."""
        required_fields = ["summary", "assumptions", "method", "recommendations", "alternatives"]
        for field in required_fields:
            self.assertIn(field, self.report, f"Missing required field: {field}")

    def test_recommendations_limit(self):
        """Verify the engine returns exactly 10 recommendations."""
        self.assertEqual(len(self.report["recommendations"]), 10, "Should return top 10 recommendations")

    def test_scoring_logic(self):
        """Verify opportunity scores are within valid range and sorted descending."""
        scores = [r["opportunity_score"] for r in self.report["recommendations"]]
        for score in scores:
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)
        
        # Check if sorted descending
        self.assertEqual(scores, sorted(scores, reverse=True), "Recommendations should be sorted by score descending")

    def test_evidence_presence(self):
        """Verify each recommendation has evidence fields."""
        for rec in self.report["recommendations"]:
            evidence = rec.get("evidence", {})
            self.assertIn("demand", evidence)
            self.assertIn("competition", evidence)
            self.assertIn("satisfaction", evidence)
            self.assertIn("momentum", evidence)

    def test_alternatives_strategies(self):
        """Verify alternatives contain the requested strategies."""
        strategies = [a["strategy"] for a in self.report["alternatives"]]
        self.assertIn("demand-heavy", strategies)
        self.assertIn("competition-light", strategies)

if __name__ == "__main__":
    unittest.main()
