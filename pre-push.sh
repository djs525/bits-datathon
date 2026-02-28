#!/bin/bash

# Configuration
BACKEND_DIR="."
FRONTEND_DIR="frontend"

echo "🚀 Starting verification..."

# 1. Backend Tests
echo "--- Running Backend Tests ---"
if ! pytest tests/test_api.py; then
    echo "❌ Backend tests failed. Please fix them before pushing."
    exit 1
fi

# 2. Frontend Tests
echo "--- Running Frontend Tests ---"
cd $FRONTEND_DIR
if ! npm test -- --watchAll=false; then
    echo "❌ Frontend tests failed. Please fix them before pushing."
    exit 1
fi
cd - > /dev/null

echo "✅ All checks passed! You are ready to push."
exit 0
