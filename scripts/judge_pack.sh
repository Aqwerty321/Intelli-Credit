#!/usr/bin/env bash
# judge_pack.sh — One-command judge pack for Intelli-Credit
# =========================================================
# Runs:  1. pytest suite (152+ tests, fails fast on any red)
#        2. Demo showdown (3 seed cases through the sync API)
#        3. Scorecard generation → reports/judge_scorecard.{md,json}
#
# Usage:
#   ./scripts/judge_pack.sh [--skip-tests] [--skip-showdown]
#
# Outputs:
#   reports/judge_scorecard.md    — human-readable summary
#   reports/judge_scorecard.json  — machine-readable for CI
#   reports/judge_pack.log        — full run log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPORTS_DIR="${ROOT}/reports"
LOG_FILE="${REPORTS_DIR}/judge_pack.log"
SKIP_TESTS=false
SKIP_SHOWDOWN=false

# Parse flags
for arg in "$@"; do
    case "$arg" in
        --skip-tests)    SKIP_TESTS=true ;;
        --skip-showdown) SKIP_SHOWDOWN=true ;;
        *) echo "Unknown flag: $arg" >&2; exit 1 ;;
    esac
done

mkdir -p "${REPORTS_DIR}"
cd "${ROOT}"

if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
fi

echo "===============================================" | tee "${LOG_FILE}"
echo "Intelli-Credit Judge Pack — $(date -u '+%Y-%m-%d %H:%M UTC')" | tee -a "${LOG_FILE}"
echo "===============================================" | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

# ─── Step 1: pytest ─────────────────────────────────────────────────────────
if [[ "${SKIP_TESTS}" == false ]]; then
    echo "Step 1/3: Running pytest…" | tee -a "${LOG_FILE}"
    python -m pytest tests/ -q --tb=short 2>&1 | tee -a "${LOG_FILE}"
    echo "" | tee -a "${LOG_FILE}"
else
    echo "Step 1/3: pytest SKIPPED (--skip-tests)" | tee -a "${LOG_FILE}"
fi

# ─── Step 2: Demo showdown ───────────────────────────────────────────────────
if [[ "${SKIP_SHOWDOWN}" == false ]]; then
    echo "Step 2/3: Running demo showdown…" | tee -a "${LOG_FILE}"
    if [[ -f "${SCRIPT_DIR}/demo_showdown.sh" ]]; then
        bash "${SCRIPT_DIR}/demo_showdown.sh" 2>&1 | tee -a "${LOG_FILE}" || {
            echo "  ⚠  Showdown failed (server may not be running) — continuing…" | tee -a "${LOG_FILE}"
        }
    else
        echo "  demo_showdown.sh not found — skipping" | tee -a "${LOG_FILE}"
    fi
    echo "" | tee -a "${LOG_FILE}"
else
    echo "Step 2/3: Showdown SKIPPED (--skip-showdown)" | tee -a "${LOG_FILE}"
fi

# ─── Step 3: Scorecard generation ────────────────────────────────────────────
echo "Step 3/3: Generating judge scorecard…" | tee -a "${LOG_FILE}"
python scripts/generate_scorecard.py \
    --cases-dir storage/cases \
    --out-dir "${REPORTS_DIR}" 2>&1 | tee -a "${LOG_FILE}"
echo "" | tee -a "${LOG_FILE}"

echo "===============================================" | tee -a "${LOG_FILE}"
echo "Judge Pack complete.  Artefacts:" | tee -a "${LOG_FILE}"
echo "  ${REPORTS_DIR}/judge_scorecard.md" | tee -a "${LOG_FILE}"
echo "  ${REPORTS_DIR}/judge_scorecard.json" | tee -a "${LOG_FILE}"
echo "  ${LOG_FILE}" | tee -a "${LOG_FILE}"
echo "===============================================" | tee -a "${LOG_FILE}"
