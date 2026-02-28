import json
import re

# Triage configuration
CATEGORIES = ["Urgent", "Decision", "Action Item", "Info", "Noise"]

# Keyword-based scoring
KEYWORDS = {
    "Urgent": ["asap", "urgent", "immediately", "deadline", "emergency", "crisis", "critical"],
    "Decision": ["decide", "approve", "signature", "confirm", "agreement", "vote", "authorise"],
    "Action Item": ["action", "do", "task", "follow up", "complete", "assign", "deliverable"],
    "Info": ["fyi", "update", "notice", "announcement", "newsletter", "minutes"],
    "Noise": ["out of office", "re:", "fwd:", "automatic reply", "vacation"]
}

def classify_message(text):
    text = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}
    
    for cat, words in KEYWORDS.items():
        for word in words:
            if word in text:
                scores[cat] += 1
                
    # Basic logic: category with highest score
    # Default to "Info" if no specific keywords
    if all(v == 0 for v in scores.values()):
        best_cat = "Info"
    else:
        best_cat = max(scores.items(), key=lambda x: x[1])[0]
        
    return best_cat, scores

def calculate_priority(text, category, sender):
    score = 0
    text = text.lower()
    
    # 1. Base score by category
    category_weights = {
        "Urgent": 80,
        "Decision": 60,
        "Action Item": 40,
        "Info": 10,
        "Noise": 0
    }
    score += category_weights.get(category, 10)
    
    # 2. Add points for specific keywords
    high_priority_words = ["critical", "asap", "due yesterday", "important"]
    for word in high_priority_words:
        if word in text:
            score += 10
            
    # 3. Contextual signals (e.g., sender authority - synthetic)
    if "@enron.com" in sender:
        score += 5
        
    # Cap score at 100
    return min(100, score)

def triage_pipeline(input_path, output_path):
    with open(input_path, 'r') as f:
        data = json.load(f)
        
    triaged_data = []
    for msg in data:
        category, scores = classify_message(msg['text'])
        priority = calculate_priority(msg['text'], category, msg['user'])
        
        msg['category'] = category
        msg['priority'] = priority
        msg['triage_scores'] = scores
        triaged_data.append(msg)
        
    with open(output_path, 'w') as f:
        json.dump(triaged_data, f, indent=2)
        
    print(f"Triaged {len(triaged_data)} messages and saved to {output_path}")

if __name__ == "__main__":
    triage_pipeline('slack_data.json', 'triaged_messages.json')
