#!/bin/bash

# PostgreSQL with pgvector Setup Script
# This script sets up PostgreSQL with pgvector using Docker

set -e

echo "=========================================="
echo "PostgreSQL with pgvector Setup"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if container already exists
if docker ps -a | grep -q agno-postgres; then
    echo "⚠️  Container 'agno-postgres' already exists."
    read -p "Do you want to remove it and create a new one? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping and removing existing container..."
        docker stop agno-postgres 2>/dev/null || true
        docker rm agno-postgres 2>/dev/null || true
    else
        echo "Starting existing container..."
        docker start agno-postgres
        echo "✓ Container started!"
        exit 0
    fi
fi

# Pull the pgvector image if not exists
echo "📦 Pulling pgvector Docker image..."
docker pull pgvector/pgvector:pg16

# Create and start the container
echo "🚀 Starting PostgreSQL container..."
docker run -d \
  --name agno-postgres \
  -e POSTGRES_USER=ai \
  -e POSTGRES_PASSWORD=ai \
  -e POSTGRES_DB=ai \
  -p 5532:5432 \
  pgvector/pgvector:pg16

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if container is running
if ! docker ps | grep -q agno-postgres; then
    echo "❌ Container failed to start. Check logs with: docker logs agno-postgres"
    exit 1
fi

# Create the vector extension
echo "📊 Creating pgvector extension..."
docker exec -it agno-postgres psql -U ai -d ai -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    echo "⚠️  Could not create extension automatically. You may need to run:"
    echo "   docker exec -it agno-postgres psql -U ai -d ai -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
}

# Verify setup
echo "🔍 Verifying setup..."
if docker exec agno-postgres psql -U ai -d ai -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';" &> /dev/null; then
    echo ""
    echo "=========================================="
    echo "✓ Setup complete!"
    echo "=========================================="
    echo ""
    echo "Connection details:"
    echo "  Host: localhost"
    echo "  Port: 5532"
    echo "  User: ai"
    echo "  Password: ai"
    echo "  Database: ai"
    echo ""
    echo "Connection string:"
    echo "  postgresql+psycopg://ai:ai@localhost:5532/ai"
    echo ""
    echo "Useful commands:"
    echo "  Stop:    docker stop agno-postgres"
    echo "  Start:   docker start agno-postgres"
    echo "  Logs:    docker logs agno-postgres"
    echo "  Remove:  docker rm -f agno-postgres"
    echo ""
else
    echo "⚠️  Setup completed but verification failed. Check logs: docker logs agno-postgres"
fi

