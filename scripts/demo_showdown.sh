#!/usr/bin/env bash
# =============================================================================
# demo_showdown.sh — Intelli-Credit Phase 2 Demo Runner
# =============================================================================
# Runs the three canonical demo cases against a live API server, prints a
# verdict table, and exits non-zero if any actual result diverges from expected.
#
# Usage:
#   ./scripts/demo_showdown.sh [--base-url http://localhost:8000]
#
# Prerequisites:
#   - API server running: uvicorn app.main:app --port 8000
#   - jq installed: sudo apt install -y jq
# =============================================================================
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DEMO_DOCS="$REPO_ROOT/demo/docs"

# Colour codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # No Colour

declare -A RESULTS
PASS=0
FAIL=0

separator() { printf '%0.s─' {1..68}; printf '\n'; }

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

check_deps() {
    if ! command -v jq &>/dev/null; then
        echo "ERROR: jq is required. Install with: sudo apt install -y jq"
        exit 1
    fi
    if ! curl -sf "$BASE_URL/health" &>/dev/null; then
        echo "ERROR: API server not reachable at $BASE_URL"
        echo "Start it with: uvicorn app.main:app --host 0.0.0.0 --port 8000"
        exit 1
    fi
}

# Run a single case end-to-end
# run_case <label> <company_name> <loan_amount> <loan_purpose> <sector> <expected> <doc_dir>
run_case() {
    local label="$1"
    local company="$2"
    local loan="$3"
    local purpose="$4"
    local sector="$5"
    local expected="$6"
    local doc_dir="$7"

    log_info "Running case: $company (expected: $expected)"

    # 1. Create case
    local create_resp
    create_resp=$(curl -sf -X POST "$BASE_URL/api/cases/" \
        -H "Content-Type: application/json" \
        -d "{
            \"company_name\": \"$company\",
            \"loan_amount\": $loan,
            \"loan_purpose\": \"$purpose\",
            \"sector\": \"$sector\"
        }")
    local case_id
    case_id=$(echo "$create_resp" | jq -r '.case_id')

    if [[ -z "$case_id" || "$case_id" == "null" ]]; then
        log_fail "Failed to create case for $company"
        RESULTS["$label"]="ERROR (case creation failed)"
        (( FAIL++ )) || true
        return
    fi
    log_info "  Case ID: $case_id"

    # 2. Upload document
    local doc_path="$doc_dir/case_facts.md"
    if [[ ! -f "$doc_path" ]]; then
        log_warn "  No document at $doc_path — skipping upload"
    else
        curl -sf -X POST "$BASE_URL/api/cases/$case_id/documents" \
            -F "file=@$doc_path" > /dev/null
        log_info "  Document uploaded: $doc_path"
    fi

    # 3. Run pipeline (synchronous)
    log_info "  Running pipeline (this may take 20-60s including LLM)..."
    local run_resp
    run_resp=$(curl -sf -m 180 -X POST "$BASE_URL/api/run/$case_id")

    local actual
    actual=$(echo "$run_resp" | jq -r '.recommendation // "ERROR"')
    local risk_score
    risk_score=$(echo "$run_resp" | jq -r '.risk_score // "?"')
    local rules_fired
    rules_fired=$(echo "$run_resp" | jq -r '.rules_fired_count // "?"')

    RESULTS["$label"]="${actual}|${risk_score}|${rules_fired}|${expected}"

    if [[ "$actual" == "$expected" ]]; then
        (( PASS++ )) || true
        log_ok "  VERDICT: $actual (risk_score=$risk_score, rules_fired=$rules_fired) ✓"
    else
        (( FAIL++ )) || true
        log_fail "  VERDICT: $actual ≠ expected $expected (risk_score=$risk_score)"
    fi
}

# ─── Main ────────────────────────────────────────────────────────────────────

echo ""
separator
echo -e "  ${BLUE}Intelli-Credit — Demo Showdown${NC}"
separator
echo ""

check_deps

run_case "APPROVE"      "Sunrise Textiles Pvt Ltd"           5000000  "Working Capital"   "textile manufacturing"    "APPROVE"      "$DEMO_DOCS/case_approve"
run_case "CONDITIONAL"  "Apex Steel Components Ltd"          15000000 "Term Loan"         "steel manufacturing"      "CONDITIONAL"  "$DEMO_DOCS/case_conditional"
run_case "REJECT"       "Greenfield Pharma Industries Pvt Ltd" 25000000 "Equipment Finance" "pharmaceutical chemicals" "REJECT"       "$DEMO_DOCS/case_reject"

echo ""
separator
echo -e "  ${BLUE}VERDICT TABLE${NC}"
separator
printf "  %-35s  %-12s  %-12s  %-10s  %-6s\n" "Company" "Expected" "Actual" "Risk Score" "Rules"
printf "  %-35s  %-12s  %-12s  %-10s  %-6s\n" "-------" "--------" "------" "----------" "-----"

ALL_PASS=true
for label in "APPROVE" "CONDITIONAL" "REJECT"; do
    IFS='|' read -r actual risk_score rules expected <<< "${RESULTS[$label]:-ERROR|?|?|$label}"
    if [[ "$actual" == "$expected" ]]; then
        status="${GREEN}✓${NC}"
    else
        status="${RED}✗${NC}"
        ALL_PASS=false
    fi
    case "$label" in
        APPROVE)      company="Sunrise Textiles Pvt Ltd";;
        CONDITIONAL)  company="Apex Steel Components Ltd";;
        REJECT)       company="Greenfield Pharma Industries";;
    esac
    printf "  %-35s  %-12s  %-12s  %-10s  %-6s  %b\n" \
        "$company" "$expected" "$actual" "$risk_score" "$rules" "$status"
done

separator
echo ""
echo -e "  Results: ${GREEN}$PASS PASS${NC}  ${RED}$FAIL FAIL${NC}"
echo ""

if [[ "$ALL_PASS" == "true" ]]; then
    echo -e "  ${GREEN}✓ ALL CASES MATCH EXPECTED VERDICTS${NC}"
    exit 0
else
    echo -e "  ${RED}✗ MISMATCH DETECTED — check output above${NC}"
    exit 1
fi
