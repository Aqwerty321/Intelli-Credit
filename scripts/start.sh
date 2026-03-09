#!/usr/bin/env bash
# start.sh — One-command startup for Intelli-Credit
# Usage: ./scripts/start.sh [--no-frontend]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "=== Intelli-Credit Startup ==="
echo "Project root: ${PROJECT_ROOT}"

# Activate venv
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
    echo "✓ Python venv activated"
else
    echo "WARNING: No .venv found. Using system python."
fi

# Check SearXNG
if docker ps 2>/dev/null | grep -q searxng; then
    echo "✓ SearXNG running"
else
    echo "Starting SearXNG..."
    docker compose up -d searxng 2>/dev/null || echo "  (docker compose not available — SearXNG may need manual start)"
fi

# Build frontend if needed
FRONTEND_DIST="${PROJECT_ROOT}/frontend/dist"
if [[ ! -d "${FRONTEND_DIST}" ]]; then
    echo "Building frontend..."
    cd "${PROJECT_ROOT}/frontend"
    npm install --silent 2>/dev/null || true
    npm run build
    cd "${PROJECT_ROOT}"
fi

echo ""
echo "--- Starting FastAPI backend on http://localhost:8000 ---"
echo "--- API docs: http://localhost:8000/docs ---"
echo ""

# Start uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Optionally start Vite dev server for frontend development
if [[ "${1:-}" != "--no-frontend" ]] && command -v node &>/dev/null; then
    sleep 1
    echo ""
    echo "--- Starting Vite dev server on http://localhost:5173 ---"
    cd "${PROJECT_ROOT}/frontend"
    npm run dev &
    FRONTEND_PID=$!
    cd "${PROJECT_ROOT}"
fi

echo ""
echo "=== Services Started ==="
echo "  Backend API:  http://localhost:8000"
echo "  API Docs:     http://localhost:8000/docs"
echo "  Frontend Dev: http://localhost:5173 (if started)"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

# Wait and cleanup on exit
trap "kill ${BACKEND_PID:-} ${FRONTEND_PID:-} 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
