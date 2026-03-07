#!/usr/bin/env bash
###############################################################################
# bootstrap.sh — Intelli-Credit environment bootstrap
# Installs: Docker CE, docker-compose-plugin, NVIDIA Container Toolkit,
#           pyenv build prerequisites, poppler-utils, OpenCV deps
# Target:   WSL2 Ubuntu 22.04+ / RTX 5090 (Blackwell sm_100) / CUDA 13.1
# Idempotent: safe to re-run
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/bootstrap"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/bootstrap_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }
err() { log "ERROR: $*"; }

log "=== Intelli-Credit Bootstrap START ==="
log "Host: $(uname -a)"
log "Project root: $PROJECT_ROOT"

###############################################################################
# 1. APT prerequisites
###############################################################################
log "--- Step 1: APT prerequisites ---"
sudo apt-get update -qq
sudo apt-get install -y -qq \
  ca-certificates curl gnupg lsb-release apt-transport-https \
  build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
  libsqlite3-dev llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev \
  libffi-dev liblzma-dev git wget unzip jq \
  poppler-utils libpoppler-dev \
  libopencv-dev python3-opencv \
  libvips-dev \
  cmake ninja-build \
  2>&1 | tail -5 | tee -a "$LOG_FILE"
log "APT prerequisites installed."

###############################################################################
# 2. Docker CE + docker-compose-plugin (skip if already installed)
###############################################################################
log "--- Step 2: Docker CE ---"
if command -v docker &>/dev/null; then
  log "Docker already installed: $(docker --version)"
else
  log "Installing Docker CE..."
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg 2>/dev/null || true
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
    https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin \
    2>&1 | tail -3 | tee -a "$LOG_FILE"
  sudo systemctl enable --now docker 2>/dev/null || true
  log "Docker installed: $(docker --version)"
fi

# Ensure current user can run docker without sudo
if ! groups | grep -q docker; then
  sudo usermod -aG docker "$USER"
  log "Added $USER to docker group. You may need to re-login for group to take effect."
fi

###############################################################################
# 3. NVIDIA Container Toolkit (skip if already installed)
###############################################################################
log "--- Step 3: NVIDIA Container Toolkit ---"
if dpkg -l | grep -q nvidia-container-toolkit; then
  log "nvidia-container-toolkit already installed."
else
  log "Installing NVIDIA Container Toolkit..."
  # Add NVIDIA repo
  distribution=$(. /etc/os-release; echo "${ID}${VERSION_ID}" | sed 's/\.//g')
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true

  # Try the standard repo URL pattern
  curl -s -L "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list" \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null 2>&1 || {
      err "Failed to add NVIDIA repo. Trying alternate method..."
      # Fallback: direct apt repo add
      echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/ubuntu22.04/amd64 /" \
        | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
    }

  sudo apt-get update -qq
  sudo apt-get install -y -qq nvidia-container-toolkit 2>&1 | tail -3 | tee -a "$LOG_FILE"
  log "nvidia-container-toolkit installed."
fi

# Configure Docker daemon for GPU access
log "Configuring Docker GPU runtime..."
if command -v nvidia-ctk &>/dev/null; then
  sudo nvidia-ctk runtime configure --runtime=docker 2>&1 | tee -a "$LOG_FILE" || true
  sudo systemctl restart docker 2>/dev/null || true
  log "nvidia-ctk runtime configured."
else
  log "nvidia-ctk not found. Configuring daemon.json manually..."
  sudo mkdir -p /etc/docker
  if [ ! -f /etc/docker/daemon.json ] || ! grep -q nvidia /etc/docker/daemon.json 2>/dev/null; then
    cat <<'DAEMONJSON' | sudo tee /etc/docker/daemon.json
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "default-runtime": "nvidia"
}
DAEMONJSON
    sudo systemctl restart docker 2>/dev/null || true
    log "daemon.json written with nvidia runtime."
  else
    log "daemon.json already contains nvidia runtime config."
  fi
fi

###############################################################################
# 4. Verify GPU passthrough
###############################################################################
log "--- Step 4: GPU passthrough verification ---"
if docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi 2>&1 | tee -a "$LOG_FILE"; then
  log "GPU passthrough: SUCCESS"
else
  err "GPU passthrough test failed. Check NVIDIA driver and container toolkit."
  err "Try: nvidia-smi (host) first. If that works, check /etc/docker/daemon.json."
  log "Continuing bootstrap — GPU tests can be re-run later."
fi

###############################################################################
# 5. pyenv prerequisites (install pyenv in setup_pyenv.sh)
###############################################################################
log "--- Step 5: pyenv build dependencies (already installed in Step 1) ---"
log "pyenv build deps ready. Run scripts/setup_pyenv.sh next."

###############################################################################
# 6. Additional tools
###############################################################################
log "--- Step 6: Additional tools ---"
# Tesseract (fallback OCR)
if ! command -v tesseract &>/dev/null; then
  sudo apt-get install -y -qq tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin 2>&1 | tail -2 | tee -a "$LOG_FILE"
  log "Tesseract installed."
else
  log "Tesseract already installed: $(tesseract --version 2>&1 | head -1)"
fi

# Java (needed by Tabula)
if ! command -v java &>/dev/null; then
  sudo apt-get install -y -qq default-jre-headless 2>&1 | tail -2 | tee -a "$LOG_FILE"
  log "Java JRE installed (for Tabula)."
else
  log "Java already installed: $(java -version 2>&1 | head -1)"
fi

###############################################################################
# Summary
###############################################################################
log "=== Intelli-Credit Bootstrap COMPLETE ==="
log "Log saved to: $LOG_FILE"
log ""
log "Next steps:"
log "  1. Re-login or run 'newgrp docker' if docker group was just added"
log "  2. Run: bash scripts/setup_pyenv.sh"
log "  3. Run: bash scripts/build_llama_cuda.sh"

cat <<EOF

{ "task": "bootstrap", "status": "done", "artifacts": ["scripts/bootstrap.sh", "logs/bootstrap/"], "errors": [], "provenance": "knowledge_blocks/bootstrap.md" }
EOF
