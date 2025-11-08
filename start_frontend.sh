#!/bin/bash

# Start the React frontend

echo "Starting Agno Chatbot Frontend..."
echo "================================="

cd "$(dirname "$0")/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the frontend
npm run dev

