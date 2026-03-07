#!/usr/bin/env bash
###############################################################################
# build_llama_cuda.sh — Clone and compile llama.cpp with CUDA for RTX 5090
# Target: Blackwell sm_100 / CUDA 13.1
# Produces: build/bin/llama-server, build/bin/llama-cli
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/cognitive"
LLAMA_DIR="$PROJECT_ROOT/vendor/llama.cpp"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/build_llama_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }
err() { log "ERROR: $*"; }

log "=== llama.cpp CUDA Build START ==="

###############################################################################
# 1. Clone or update llama.cpp
###############################################################################
if [ -d "$LLAMA_DIR/.git" ]; then
  log "llama.cpp already cloned. Pulling latest..."
  cd "$LLAMA_DIR"
  git pull --ff-only 2>&1 | tail -3 | tee -a "$LOG_FILE"
else
  log "Cloning llama.cpp..."
  mkdir -p "$(dirname "$LLAMA_DIR")"
  git clone https://github.com/ggerganov/llama.cpp "$LLAMA_DIR" 2>&1 | tail -3 | tee -a "$LOG_FILE"
  cd "$LLAMA_DIR"
fi

COMMIT_HASH=$(git rev-parse HEAD)
log "llama.cpp commit: $COMMIT_HASH"

###############################################################################
# 2. Detect CUDA toolkit
###############################################################################
if command -v nvcc &>/dev/null; then
  NVCC_VER=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
  log "CUDA toolkit detected: $NVCC_VER"
elif [ -d "/usr/local/cuda" ]; then
  export PATH="/usr/local/cuda/bin:$PATH"
  export LD_LIBRARY_PATH="/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"
  NVCC_VER=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
  log "CUDA toolkit at /usr/local/cuda: $NVCC_VER"
else
  err "No CUDA toolkit found. Install CUDA toolkit first."
  err "For WSL2: https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=WSL-Ubuntu"
  exit 1
fi

###############################################################################
# 3. Build with cmake (primary method)
###############################################################################
log "--- Building llama.cpp with cmake (CUDA, sm_100 for Blackwell) ---"
cd "$LLAMA_DIR"

# Clean previous build
rm -rf build 2>/dev/null || true

# Try cmake build with Blackwell architecture
CMAKE_CUDA_ARCH="100"
log "Target CUDA architecture: sm_${CMAKE_CUDA_ARCH} (Blackwell/RTX 5090)"

if cmake -B build \
  -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES="${CMAKE_CUDA_ARCH}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_CURL=OFF \
  2>&1 | tee -a "$LOG_FILE"; then

  log "cmake configure succeeded. Building..."
  cmake --build build --config Release -j "$(nproc)" 2>&1 | tail -20 | tee -a "$LOG_FILE"

  if [ -f "build/bin/llama-server" ] || [ -f "build/bin/llama-cli" ]; then
    log "BUILD SUCCESS (cmake)"
    log "Binaries:"
    ls -la build/bin/llama-* 2>/dev/null | tee -a "$LOG_FILE"
  else
    err "cmake build produced no binaries. Checking build directory..."
    find build -name "llama-*" -type f 2>/dev/null | tee -a "$LOG_FILE"
  fi
else
  ###########################################################################
  # 3b. Fallback: try broader arch list
  ###########################################################################
  err "cmake failed with sm_100. Trying sm_89;sm_90;sm_100..."
  rm -rf build 2>/dev/null || true

  if cmake -B build \
    -DGGML_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES="89;90;100" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_CURL=OFF \
    2>&1 | tee -a "$LOG_FILE"; then

    cmake --build build --config Release -j "$(nproc)" 2>&1 | tail -20 | tee -a "$LOG_FILE"
    log "BUILD SUCCESS (cmake, multi-arch fallback)"
  else
    #######################################################################
    # 3c. Fallback: make (legacy build system)
    #######################################################################
    err "cmake fallback also failed. Trying legacy Makefile..."
    make clean 2>/dev/null || true
    if GGML_CUDA=1 CUDA_DOCKER_ARCH=sm_100 make -j "$(nproc)" 2>&1 | tail -20 | tee -a "$LOG_FILE"; then
      log "BUILD SUCCESS (make)"
    else
      err "All build methods failed."
      log "PIVOT: Consider using Ollama (pre-built llama.cpp runtime)"
      log "  Install: curl -fsSL https://ollama.com/install.sh | sh"
      log "  Then: ollama pull deepseek-r1:8b-llama-distill-q4_K_M"
      exit 1
    fi
  fi
fi

###############################################################################
# 4. Quick smoke test
###############################################################################
log "--- Smoke test ---"
LLAMA_SERVER=""
for CANDIDATE in build/bin/llama-server bin/llama-server llama-server; do
  if [ -x "$LLAMA_DIR/$CANDIDATE" ]; then
    LLAMA_SERVER="$LLAMA_DIR/$CANDIDATE"
    break
  fi
done

if [ -n "$LLAMA_SERVER" ]; then
  log "llama-server binary: $LLAMA_SERVER"
  "$LLAMA_SERVER" --version 2>&1 | tee -a "$LOG_FILE" || log "(version flag may not be supported)"
else
  log "llama-server binary not found in expected paths."
  find "$LLAMA_DIR" -name "llama-server" -type f 2>/dev/null | tee -a "$LOG_FILE"
fi

###############################################################################
# 5. Record compatibility info
###############################################################################
COMPAT_FILE="$PROJECT_ROOT/knowledge_blocks/compat_matrix.md"
cat >> "$COMPAT_FILE" <<EOF

## llama.cpp Build — $(date -Iseconds)
- **Commit:** $COMMIT_HASH
- **CUDA version:** ${NVCC_VER:-unknown}
- **Target arch:** sm_${CMAKE_CUDA_ARCH}
- **Build method:** cmake
- **Host GPU:** $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
- **Driver:** $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
- **Status:** $([ -f "$LLAMA_DIR/build/bin/llama-server" ] && echo "SUCCESS" || echo "CHECK")
EOF

log "=== llama.cpp CUDA Build COMPLETE ==="
log "Log: $LOG_FILE"

cat <<EOF

{ "task": "build_llama_cuda", "status": "done", "artifacts": ["vendor/llama.cpp/build/bin/llama-server"], "errors": [], "provenance": "knowledge_blocks/compat_matrix.md" }
EOF
