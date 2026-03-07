#!/usr/bin/env bash
###############################################################################
# setup_pyenv.sh — Install pyenv + create isolated Python environments
# Creates: py310-pyreason (3.10.13) and py312-glmocr (3.12.7)
# Idempotent: safe to re-run
###############################################################################
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs/bootstrap"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/setup_pyenv_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

log "=== pyenv Setup START ==="

###############################################################################
# 1. Install pyenv (if not present)
###############################################################################
export PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"

if [ -d "$PYENV_ROOT" ] && [ -x "$PYENV_ROOT/bin/pyenv" ]; then
  log "pyenv already installed at $PYENV_ROOT"
else
  log "Installing pyenv..."
  curl -fsSL https://pyenv.run | bash 2>&1 | tail -5 | tee -a "$LOG_FILE"
  log "pyenv installed."
fi

# Ensure pyenv is on PATH for this session
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)" 2>/dev/null || true
eval "$(pyenv virtualenv-init -)" 2>/dev/null || true

# Add to shell RC if not already present
for RC_FILE in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$RC_FILE" ]; then
    if ! grep -q 'PYENV_ROOT' "$RC_FILE" 2>/dev/null; then
      log "Adding pyenv init to $RC_FILE"
      cat >> "$RC_FILE" <<'PYENVRC'

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)" 2>/dev/null || true
PYENVRC
    fi
  fi
done

log "pyenv version: $(pyenv --version)"

###############################################################################
# 2. Install Python versions
###############################################################################
PY310="3.10.13"
PY312="3.12.7"

for VER in "$PY310" "$PY312"; do
  if pyenv versions --bare | grep -qx "$VER"; then
    log "Python $VER already installed."
  else
    log "Installing Python $VER (this may take a few minutes)..."
    pyenv install "$VER" 2>&1 | tail -3 | tee -a "$LOG_FILE"
    log "Python $VER installed."
  fi
done

###############################################################################
# 3. Create virtualenvs
###############################################################################
VENVS=("py310-pyreason:$PY310" "py312-glmocr:$PY312")

for ENTRY in "${VENVS[@]}"; do
  VENV_NAME="${ENTRY%%:*}"
  VENV_VER="${ENTRY##*:}"
  if pyenv versions --bare | grep -q "$VENV_NAME"; then
    log "Virtualenv $VENV_NAME already exists."
  else
    log "Creating virtualenv $VENV_NAME ($VENV_VER)..."
    pyenv virtualenv "$VENV_VER" "$VENV_NAME" 2>&1 | tee -a "$LOG_FILE"
    log "Virtualenv $VENV_NAME created."
  fi
done

###############################################################################
# 4. Write .python-version files in service directories
###############################################################################
declare -A SERVICE_ENVS=(
  ["services/reasoning"]="py310-pyreason"
  ["services/ingestor"]="py312-glmocr"
  ["services/cognitive"]="py312-glmocr"
  ["services/lakehouse"]="py312-glmocr"
  ["services/entity_resolution"]="py312-glmocr"
  ["services/graph"]="py312-glmocr"
  ["services/agents"]="py312-glmocr"
  ["services/cam"]="py312-glmocr"
)

for DIR in "${!SERVICE_ENVS[@]}"; do
  FULL_DIR="$PROJECT_ROOT/$DIR"
  mkdir -p "$FULL_DIR"
  echo "${SERVICE_ENVS[$DIR]}" > "$FULL_DIR/.python-version"
  log "Wrote $DIR/.python-version → ${SERVICE_ENVS[$DIR]}"
done

# Also set project root to py312-glmocr (main env)
echo "py312-glmocr" > "$PROJECT_ROOT/.python-version"
log "Wrote .python-version → py312-glmocr (project root)"

###############################################################################
# 5. Install base packages in each environment
###############################################################################
log "--- Installing base packages in py312-glmocr ---"
PYENV_VERSION=py312-glmocr pyenv exec pip install --upgrade pip setuptools wheel 2>&1 | tail -2 | tee -a "$LOG_FILE"

log "--- Installing base packages in py310-pyreason ---"
PYENV_VERSION=py310-pyreason pyenv exec pip install --upgrade pip setuptools wheel 2>&1 | tail -2 | tee -a "$LOG_FILE"

###############################################################################
# Summary
###############################################################################
log "=== pyenv Setup COMPLETE ==="
log "Environments:"
pyenv versions 2>&1 | tee -a "$LOG_FILE"
log ""
log "Next steps:"
log "  1. Activate environment: pyenv activate py312-glmocr"
log "  2. Install service-specific packages per service README"

cat <<EOF

{ "task": "setup_pyenv", "status": "done", "artifacts": ["scripts/setup_pyenv.sh", ".python-version files"], "errors": [] }
EOF
