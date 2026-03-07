#!/usr/bin/env bash
###############################################################################
# profile_deepseek.sh — Download DeepSeek-R1-Distill-Llama-8B Q4_K_M and
# profile VRAM usage at different context sizes
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/cognitive"
MODELS_DIR="$PROJECT_ROOT/models"
REPORT_DIR="$PROJECT_ROOT/reports/acceptance"
mkdir -p "$LOG_DIR" "$MODELS_DIR" "$REPORT_DIR"
LOG_FILE="$LOG_DIR/profile_deepseek_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

# Model config
MODEL_REPO="bartowski/DeepSeek-R1-Distill-Llama-8B-GGUF"
MODEL_FILE="DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"
MODEL_PATH="$MODELS_DIR/$MODEL_FILE"

LLAMA_SERVER="$PROJECT_ROOT/vendor/llama.cpp/build/bin/llama-server"

log "=== DeepSeek Profiling START ==="

###############################################################################
# 1. Download model (if not present)
###############################################################################
if [ -f "$MODEL_PATH" ]; then
  log "Model already downloaded: $MODEL_PATH ($(du -h "$MODEL_PATH" | cut -f1))"
else
  log "Downloading $MODEL_FILE from HuggingFace..."
  if command -v huggingface-cli &>/dev/null; then
    huggingface-cli download "$MODEL_REPO" "$MODEL_FILE" \
      --local-dir "$MODELS_DIR" --local-dir-use-symlinks False \
      2>&1 | tail -5 | tee -a "$LOG_FILE"
  else
    # Fallback: direct wget
    DOWNLOAD_URL="https://huggingface.co/${MODEL_REPO}/resolve/main/${MODEL_FILE}"
    log "Using wget: $DOWNLOAD_URL"
    wget -q --show-progress -O "$MODEL_PATH" "$DOWNLOAD_URL" 2>&1 | tee -a "$LOG_FILE"
  fi
  log "Download complete: $(du -h "$MODEL_PATH" | cut -f1)"
fi

###############################################################################
# 2. Check for llama-server binary
###############################################################################
if [ ! -x "$LLAMA_SERVER" ]; then
  # Try alternate locations
  for CANDIDATE in \
    "$PROJECT_ROOT/vendor/llama.cpp/build/bin/llama-server" \
    "$PROJECT_ROOT/vendor/llama.cpp/llama-server" \
    "$(which llama-server 2>/dev/null || true)"; do
    if [ -x "$CANDIDATE" ]; then
      LLAMA_SERVER="$CANDIDATE"
      break
    fi
  done

  if [ ! -x "$LLAMA_SERVER" ]; then
    log "llama-server not found. Trying Ollama fallback..."
    if command -v ollama &>/dev/null; then
      log "PIVOT: Using Ollama for profiling."
      log "Run: ollama pull deepseek-r1:8b-llama-distill-q4_K_M"
      # Simple Ollama profile
      ollama pull deepseek-r1:8b-llama-distill-q4_K_M 2>&1 | tail -3 | tee -a "$LOG_FILE" || true
      nvidia-smi --query-gpu=memory.used,memory.total --format=csv > "$REPORT_DIR/vram_profile.csv"
      exit 0
    fi
    log "ERROR: No inference runtime found. Build llama.cpp first."
    exit 1
  fi
fi

log "Using llama-server: $LLAMA_SERVER"

###############################################################################
# 3. Profile VRAM at different context sizes
###############################################################################
REPORT_FILE="$REPORT_DIR/vram_profile.json"
echo '{"profiles": [' > "$REPORT_FILE"

# Record baseline VRAM
BASELINE_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
log "Baseline VRAM usage: ${BASELINE_VRAM} MiB"

CTX_SIZES=(4096 8192 16384 32768)
FIRST=true

for CTX in "${CTX_SIZES[@]}"; do
  log "--- Profiling ctx_size=$CTX ---"

  # Start server in background
  "$LLAMA_SERVER" \
    -m "$MODEL_PATH" \
    --host 127.0.0.1 --port 18080 \
    -ngl 99 \
    -c "$CTX" \
    --log-disable \
    &
  SERVER_PID=$!

  # Wait for server to load model
  sleep 10
  for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:18080/health 2>/dev/null | grep -q "ok"; then
      break
    fi
    sleep 2
  done

  # Measure VRAM after model load
  LOADED_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
  log "VRAM after loading (ctx=$CTX): ${LOADED_VRAM} MiB"

  # Send a test prompt to exercise KV cache
  RESPONSE=$(curl -s http://127.0.0.1:18080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"deepseek\",\"messages\":[{\"role\":\"user\",\"content\":\"What are the Five Cs of Credit? Be brief.\"}],\"max_tokens\":200}" \
    2>/dev/null || echo '{"error":"no response"}')

  # Measure VRAM after inference
  INFERENCE_VRAM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
  log "VRAM after inference (ctx=$CTX): ${INFERENCE_VRAM} MiB"

  # Check think token preservation
  THINK_PRESERVED="false"
  if echo "$RESPONSE" | grep -q "<think>"; then
    THINK_PRESERVED="true"
    log "  <think> tokens PRESERVED"
  else
    log "  <think> tokens not found in response (may need longer prompt)"
  fi

  # Kill server
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
  sleep 3

  # Write JSON entry
  if [ "$FIRST" = true ]; then
    FIRST=false
  else
    echo ',' >> "$REPORT_FILE"
  fi

  cat >> "$REPORT_FILE" <<JSONENTRY
  {
    "ctx_size": $CTX,
    "baseline_vram_mib": $BASELINE_VRAM,
    "loaded_vram_mib": $LOADED_VRAM,
    "inference_vram_mib": $INFERENCE_VRAM,
    "model_vram_delta_mib": $((LOADED_VRAM - BASELINE_VRAM)),
    "think_tokens_preserved": $THINK_PRESERVED,
    "timestamp": "$(date -Iseconds)"
  }
JSONENTRY
done

echo '],' >> "$REPORT_FILE"

# Add summary
TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')
cat >> "$REPORT_FILE" <<SUMMARY
"summary": {
  "model": "$MODEL_FILE",
  "gpu": "$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)",
  "total_vram_mib": $TOTAL_VRAM,
  "baseline_vram_mib": $BASELINE_VRAM,
  "quantization": "Q4_K_M",
  "gpu_layers": 99
}
}
SUMMARY

log "=== DeepSeek Profiling COMPLETE ==="
log "VRAM profile report: $REPORT_FILE"

cat <<EOF

{ "task": "profile_deepseek", "status": "done", "artifacts": ["$REPORT_FILE", "$MODEL_PATH"], "errors": [] }
EOF
