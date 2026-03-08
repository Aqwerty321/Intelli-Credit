#!/usr/bin/env bash
# =============================================================================
# Intelli-Credit: End-to-End Demo
# Runs the full credit appraisal pipeline on test data
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    echo -e "\n${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}\n"
}

info()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; }
error()   { echo -e "  ${RED}✗${NC} $1"; }
section() { echo -e "\n  ${BOLD}── $1 ──${NC}"; }

# Activate venv
source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || true

banner "INTELLI-CREDIT: AI-Powered Credit Appraisal Engine"

echo -e "  ${BOLD}System Components:${NC}"
info "Vision OCR: PaddleOCR-VL (1.69 GB VRAM)"
info "Cognitive LLM: DeepSeek-R1-8B Q8_0 via Ollama"
info "Web Research: SearXNG (self-hosted meta-search)"
info "Reasoning: Neuro-symbolic rule engine (10 credit rules)"
info "Lakehouse: DuckDB (zero-copy Parquet/CSV analytics)"
info "Orchestration: Agent-based pipeline"

# ── Step 1: Check prerequisites ──
section "Checking Prerequisites"

# Check GPU
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1)
    info "GPU: $GPU_NAME (${GPU_FREE} MiB free)"
else
    warn "nvidia-smi not found — GPU features unavailable"
fi

# Check Ollama
OLLAMA_BASE="${OLLAMA_HOST:-http://172.23.112.1:11434}"
if curl -sf "${OLLAMA_BASE}/api/tags" >/dev/null 2>&1; then
    info "Ollama: online at ${OLLAMA_BASE}"
else
    warn "Ollama: offline — LLM assessment will be skipped"
fi

# Check SearXNG
if curl -sf "http://localhost:8888/healthz" >/dev/null 2>&1 || curl -sf "http://localhost:8888/search?q=test&format=json" >/dev/null 2>&1; then
    info "SearXNG: online at localhost:8888"
else
    warn "SearXNG: offline — starting container..."
    docker compose up -d searxng 2>/dev/null || true
    sleep 3
fi

# ── Step 2: Run the E2E pipeline ──
section "Running E2E Credit Appraisal Pipeline"

COMPANY="Apex Steel Industries Ltd."
AMOUNT=50000000
PURPOSE="Working Capital"
TEST_FILES=$(ls tests/extraction_smoke/sample_*.pdf 2>/dev/null | tr '\n' ' ')

if [ -n "$TEST_FILES" ]; then
    echo -e "  Company: ${BOLD}${COMPANY}${NC}"
    echo -e "  Loan: ${BOLD}₹${AMOUNT}${NC} for ${PURPOSE}"
    echo ""
    python services/pipeline.py \
        --input $TEST_FILES \
        --company "$COMPANY" \
        --amount $AMOUNT \
        --purpose "$PURPOSE" \
        --insights "Demo run - synthetic test data" 2>&1 | sed 's/^/  /'
else
    warn "No test PDF files found. Skipping pipeline run."
fi

# ── Step 3: Run research agent ──
section "Research Agent (SearXNG + DeepSeek)"
echo "  Running on test companies..."
python services/agents/research_agent.py 2>&1 | sed 's/^/  /'

# ── Step 4: Run all acceptance tests ──
banner "ACCEPTANCE TEST SUITE"

PASS_COUNT=0
FAIL_COUNT=0
TESTS=("extraction_smoke/test_extraction" "mem_limit/test_mem_limit" "cam/test_explainability" "research_depth/test_research" "vram_profile/test_vram")
LABELS=("Extraction Accuracy (F1≥0.9)" "Docker Mem Limits" "Explainability Coverage" "Research Depth (≥1 novel finding)" "VRAM Profile (<24GB)")

for i in "${!TESTS[@]}"; do
    TEST="${TESTS[$i]}"
    LABEL="${LABELS[$i]}"
    STATUS=$(python "acceptance/${TEST}.py" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null || echo "ERROR")
    if [ "$STATUS" = "PASS" ]; then
        info "${LABEL}: ${GREEN}PASS${NC}"
        ((PASS_COUNT+=1))
    else
        error "${LABEL}: ${RED}${STATUS}${NC}"
        ((FAIL_COUNT+=1))
    fi
done

echo ""
echo -e "  ${BOLD}Results: ${PASS_COUNT}/5 PASS, ${FAIL_COUNT}/5 FAIL${NC}"

if [ $FAIL_COUNT -eq 0 ]; then
    banner "ALL ACCEPTANCE TESTS PASSED ✓"
else
    echo -e "\n  ${RED}${BOLD}Some tests failed. Check output above.${NC}\n"
fi

# ── Summary ──
section "Output Artifacts"
echo "  CAM outputs:      storage/processed/cam_outputs/"
echo "  Research results:  storage/processed/research_results/"
echo "  Extraction data:   storage/processed/extraction_results/"
echo "  VRAM profile:      reports/acceptance/vram_profile.json"
echo "  Lakehouse DB:      storage/lakehouse/intelli_credit.duckdb"
echo ""
info "Demo complete."
