#!/usr/bin/env bash
###############################################################################
# run_acceptance.sh — Run all acceptance tests and output JSON to reports/
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports/acceptance"
mkdir -p "$REPORT_DIR"

export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)" 2>/dev/null || true

log() { echo "[$(date -Iseconds)] $*"; }

log "=== Acceptance Test Suite START ==="

PASS_COUNT=0
FAIL_COUNT=0
RESULTS='[]'

run_test() {
  local TEST_NAME="$1"
  local TEST_SCRIPT="$2"
  local REPORT_FILE="$REPORT_DIR/${TEST_NAME}.json"

  log "--- Running: $TEST_NAME ---"
  if PYENV_VERSION=py312-glmocr pyenv exec python "$TEST_SCRIPT" > "$REPORT_FILE" 2>&1; then
    log "  PASS: $TEST_NAME"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    log "  FAIL: $TEST_NAME (exit code: $?)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    # Write failure report if script didn't
    if [ ! -s "$REPORT_FILE" ]; then
      echo "{\"test\": \"$TEST_NAME\", \"status\": \"FAIL\", \"error\": \"script exited with non-zero code\"}" > "$REPORT_FILE"
    fi
  fi
}

###############################################################################
# 1. Extraction Accuracy
###############################################################################
run_test "extraction_accuracy" "$PROJECT_ROOT/acceptance/extraction_smoke/test_extraction.py"

###############################################################################
# 2. Research Depth
###############################################################################
run_test "research_depth" "$PROJECT_ROOT/acceptance/research_depth/test_research.py"

###############################################################################
# 3. Explainability Coverage
###############################################################################
run_test "explainability_coverage" "$PROJECT_ROOT/acceptance/cam/test_explainability.py"

###############################################################################
# 4. VRAM Profiling
###############################################################################
run_test "vram_profile" "$PROJECT_ROOT/acceptance/vram_profile/test_vram.py"

###############################################################################
# 5. Mem Limit Enforcement
###############################################################################
run_test "mem_limit_enforcement" "$PROJECT_ROOT/acceptance/mem_limit/test_mem_limit.py"

###############################################################################
# Summary
###############################################################################
TOTAL=$((PASS_COUNT + FAIL_COUNT))
SUMMARY_FILE="$REPORT_DIR/summary.json"

cat > "$SUMMARY_FILE" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "total_tests": $TOTAL,
  "passed": $PASS_COUNT,
  "failed": $FAIL_COUNT,
  "pass_rate": $(echo "scale=2; $PASS_COUNT * 100 / $TOTAL" | bc 2>/dev/null || echo "0"),
  "reports_dir": "$REPORT_DIR",
  "tests": [
    "extraction_accuracy",
    "research_depth",
    "explainability_coverage",
    "vram_profile",
    "mem_limit_enforcement"
  ]
}
EOF

log "=== Acceptance Test Suite COMPLETE ==="
log "Results: $PASS_COUNT/$TOTAL passed"
log "Reports: $REPORT_DIR/"

cat "$SUMMARY_FILE"
