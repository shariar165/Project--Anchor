#!/bin/bash
# One-command local development startup for Anchor AI.
# Requires: Docker Desktop running, Python venvs set up in each service.

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting infrastructure (db + redis)..."
docker-compose -f "$REPO_ROOT/docker-compose.yml" up -d db redis

echo "Waiting for DB to be healthy..."
until docker-compose -f "$REPO_ROOT/docker-compose.yml" exec -T db pg_isready -U anchor -d anchor_db > /dev/null 2>&1; do
  sleep 1
done

echo "Starting RAG service on :8001..."
(cd "$REPO_ROOT/services/rag" && .venv/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8001 --reload) &
RAG_PID=$!

echo "Starting Core API on :8000..."
(cd "$REPO_ROOT/services/api" && RAG_SERVICE_URL=http://localhost:8001 .venv/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8000 --reload) &
API_PID=$!

echo ""
echo "Anchor AI is running:"
echo "  Core API:     http://localhost:8000"
echo "  API docs:     http://localhost:8000/docs"
echo "  RAG service:  http://localhost:8001"
echo "  RAG health:   http://localhost:8001/health"
echo "  Student app:  serve apps/student/ on :8080"
echo "  Admin panel:  serve apps/admin/ on :8081"
echo ""
echo "Press Ctrl+C to stop all services."

cleanup() {
  echo "Stopping services..."
  kill $RAG_PID $API_PID 2>/dev/null
  docker-compose -f "$REPO_ROOT/docker-compose.yml" stop db redis
}
trap cleanup EXIT

wait
