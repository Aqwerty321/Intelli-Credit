#!/usr/bin/env bash
# run_acceptance.sh — Run full pytest acceptance suite
# Usage: ./scripts/run_acceptance.sh [pytest args]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

echo "=== Intelli-Credit Acceptance Tests (pytest) ==="
echo ""

python -m pytest tests/ -v --tb=short "$@"

echo ""
echo "=== Done ==="
