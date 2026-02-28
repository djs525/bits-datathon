import pytest
from triage import classify_message, calculate_priority

def test_classify_message_urgent():
    text = "This is an URGENT matter, please respond ASAP"
    cat, scores = classify_message(text)
    assert cat == "Urgent"
    assert scores["Urgent"] >= 1

def test_classify_message_decision():
    text = "Please approve this signature request"
    cat, scores = classify_message(text)
    assert cat == "Decision"

def test_calculate_priority_high():
    text = "CRITICAL: deadline is today"
    priority = calculate_priority(text, "Urgent", "boss@enron.com")
    assert priority > 80

def test_calculate_priority_low():
    text = "Just a quick fyi on the weather"
    priority = calculate_priority(text, "Info", "random@gmail.com")
    assert priority < 30
