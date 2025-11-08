#!/bin/bash

# Start the FastAPI backend server

echo "Starting Agno Chatbot Backend..."
echo "================================"

cd "$(dirname "$0")"

# Check if Qdrant is running
if ! curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "⚠️  Warning: Qdrant doesn't seem to be running on port 6333"
    echo "   Start it with: docker run -d --name agno-qdrant -p 6333:6333 qdrant/qdrant"
    echo ""
fi

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Start the backend
cd backend
uvicorn api:app --reload --port 8000 --host 0.0.0.0

