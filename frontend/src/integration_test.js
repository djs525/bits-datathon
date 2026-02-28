import { api } from '../api';

const testRecommendations = async () => {
    console.log("Testing Recommendation Integration...");
    try {
        const data = await api.getRecommendations();
        console.log("✓ Successfully fetched recommendations from API");

        if (data.recommendations && data.recommendations.length === 10) {
            console.log("✓ Top 10 recommendations present");
        } else {
            console.error("✗ Failed: Expected 10 recommendations, got", data.recommendations?.length);
        }

        const top = data.recommendations[0];
        console.log(`✓ Top Recommendation: ${top.area_name} (${top.area_id}) - Score: ${top.opportunity_score}`);

    } catch (err) {
        console.error("✗ Integration Error:", err.message);
    }
};

// This matches the pattern the user might use to run a script in the frontend context if they had a test runner
// Since there's no package.json/Jest, we provide this as a manual verification script
export default testRecommendations;
