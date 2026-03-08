# CLAUDE.md — Master AI Architect Operating Directives

> **Purpose:** Definitive engineering directives for a local, zero-trust, microservices implementation of the **Intelli-Credit** decisioning engine.
> Use this file as the canonical blueprint for bootstrapping, building, and deploying the system inside a freshly created WSL (Ubuntu 22.04+) workspace.

---

## Quick start (current build)

> The system is implemented and working. Phase 3 + Phase 4 + Phase 5 complete.  
> **Test baseline: 197+ tests pass (175 Phase 4 + 22 Phase 5 backend).  Frontend Vitest: 24 unit tests.  Trace schema: v3.  Frontend: 39 modules.**

### Prerequisites
- Ollama running with `sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0:latest` at `http://172.23.112.1:11434`
- Light model `qwen2.5:3b` available in Ollama (used by Router/Judge/ClaimGraph agents)
- SearXNG Docker container running at `localhost:8888`
- Python `.venv` activated: `source .venv/bin/activate`
- Node 18+ for frontend dev

### One-command startup
```bash
./scripts/start.sh
```
This starts the FastAPI backend on `http://localhost:8000` and the Vite dev server on `http://localhost:5173`.

### Run acceptance tests
```bash
./scripts/run_acceptance.sh
# or directly:
python -m pytest tests/ -v --tb=short
```
Expected: **172+ PASS** (Phase 3 + Phase 4 tests)

### One-command judge pack (tests + showdown + scorecard)
```bash
./scripts/judge_pack.sh
# skip long tests during iteration:
./scripts/judge_pack.sh --skip-tests
```
Outputs: `reports/judge_scorecard.md`, `reports/judge_scorecard.json`, `reports/judge_pack.log`

### Frontend dev only
```bash
cd frontend && npm run dev
```

### API server only
```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Health check
```bash
curl http://localhost:8000/health        # alias
curl http://localhost:8000/api/health    # canonical
# Both return: {"status": "ok", "version": "3.0.0"}
```

---

## Rule engine v2 — critical authoring rules

> Violating these silently produces 0.0 risk_adjustment for every rule.

1. **`risk_adjustment` must be on each threshold object**, not on the `action` block.
2. **`direction: above|below`** must appear on the condition block (default: `above`).
3. Top-level `version: "2.0"` is required.

**Correct example (v2):**
```yaml
version: "2.0"
condition:
  type: threshold
  direction: above
  field: dpd_days
  thresholds:
    - value: 90
      label: critical
      risk_adjustment: 0.40
    - value: 30
      label: moderate
      risk_adjustment: 0.20
```

**Wrong (v1 — silent zero bug):**
```yaml
# NEVER DO THIS
action:
  risk_adjustment_critical: 0.40   # namespaced key — never read
  risk_adjustment_moderate: 0.20
```

---

## Research agent — key constants

- `DOMAIN_BLOCKLIST` in `services/agents/research_agent.py`: 26 domains that produce noise (Reddit, Cambridge Dictionary, Amazon, etc.). Add new noise domains here.
- `DOMAIN_TIERS`: 25-entry confidence map. RBI/SEBI = 0.95; ET/BL = 0.75; default = 0.40.
- `_entity_matches()`: requires full company name phrase OR ≥2 significant words (>4 chars) present in result text. This prevents "Apex Steel Ltd" matching recipe pages containing "steel".
- Cache path: `storage/cache/research/<sanitized_company_name>_v3_research.json`. Delete to force re-research.
- `CACHE_VERSION = "3"` — caches from earlier versions are automatically rejected and refreshed.
- `stale_findings_marked` counter: stale items (regulatory/litigation from before 2021) are kept in findings but have `stale=True` and `risk_impact` prefixed with `"stale_"`.

---

## Phase 3 + Phase 4 implementation status

### Agents (services/agents/)
| Agent | File | Status |
|---|---|---|
| ResearchAgent | `research_agent.py` | Phase 3 — noise/stale hardened, CACHE_VERSION=3 |
| ResearchRouterAgent | `research_router.py` | Phase 3 NEW — LLM search planner, deterministic fallback |
| EvidenceJudgeAgent | `evidence_judge.py` | Phase 3 NEW — composite scorer, precision@10 fixed in Phase 4 |
| ClaimGraph | `claim_graph.py` | Phase 3 NEW — claim extraction + contradiction detection |
| CounterfactualChallenger | `counterfactual.py` | Phase 3 NEW — deterministic what-if scenarios |

### Trace schema v3 (`schema_version: "v3"`)
New keys: `research_plan`, `claim_graph`, `counterfactuals`, `evidence_judge`, `orchestration_mode`, `fallbacks_used`, `orchestration_impact`.  
`v2_compat: True` preserved for backward-compatibility.

### API additions (Phase 3/4)
- `POST /api/cases/{case_id}/notes`, `GET /api/cases/{case_id}/notes` — officer notes
- `GET /health` — alias for `/api/health` (Phase 4)
- `GET /api/cases/{case_id}` now includes `officer_notes` array (Phase 4)
- SSE contract: supplemental events (`research_plan_ready`, `evidence_scored`, `claim_graph_ready`, `counterfactual_ready`) are now emitted **before** `complete` (Phase 4 fix)

### Frontend (Judge Mode)
- `CaseDetail.jsx` — Judge tab appears when `schema_version === "v3"` after a run
- Shows: Evidence Quality (precision@10, corroboration%), Claim Graph, Counterfactuals, Search Plan

---

## Phase 5 implementation status — Full Frontend Feature Access + Notes 2.0

### Backend (`app/api/cases.py`)
- `_normalize_tags(tags)` — lowercase, strip, dedupe, max-5
- `_normalize_note_record(raw)` — back-fills `tags=[]`, `pinned=False`, `updated_at=created_at` for legacy notes
- `OfficerNote` extended: `tags: list[str] = []`, `pinned: bool = False`
- `OfficerNoteRecord` extended: `tags`, `pinned`, `updated_at`
- `NoteUpdate` model added (all fields Optional)
- `PATCH /api/cases/{id}/notes/{nid}` — partial update, normalises tags, sets `updated_at`
- `DELETE /api/cases/{id}/notes/{nid}` — 204, 404 if not found
- `GET /api/cases/{id}` — `officer_notes` normalised via `_normalize_note_record`

### Frontend
| File | Change |
|---|---|
| `frontend/src/services/api.js` | NEW — centralised async API client; all endpoints |
| `frontend/src/components/ConfirmModal.jsx` | NEW — reusable danger/safe confirmation modal |
| `frontend/src/components/CaseDetail.jsx` | Notes 2.0 tab (CRUD, tags, pinned, filter OR logic), case delete, sync-run fallback, SSE error CTA, `downloadCAMUrl` |
| `frontend/src/components/CaseList.jsx` | "Actions" column with per-row delete + ConfirmModal |
| `frontend/src/App.jsx` | Health badge (Healthy/Offline), 30 s polling, version `v3.0` |

### Tests
- `tests/integration/test_phase5_notes.py` — 19 tests (creation, GET, PATCH, DELETE, edge cases)
- `tests/integration/test_phase5_e2e_flow.py` — 3 tests (full lifecycle, tag edges, 404 paths)
- `frontend/src/test/ConfirmModal.test.jsx` — 8 Vitest unit tests
- `frontend/src/test/HealthBadge.test.jsx` — 4 Vitest unit tests
- `frontend/src/test/CaseListDelete.test.jsx` — 5 Vitest unit tests
- `frontend/src/test/NotesList.test.jsx` — 7 Vitest unit tests
- `frontend/e2e/judge_demo.spec.js` — 11 Playwright E2E smoke tests (requires live servers)

### Run Vitest
```bash
cd frontend && npm test
# Expected: 24 tests pass
```

### Run Playwright E2E (requires live servers)
```bash
# In one terminal:
./scripts/start.sh
# In another:
cd frontend && npm run e2e
```

### Feature access matrix
See `docs/feature_access_matrix.md` for a full backend-endpoint → UI-component mapping.

---

## Demo seed data

`demo/seed/` — three JSON cases ready to load through the UI or API:
- `case_approve.json` — Sunrise Textiles (clean, CMR 3, no DPD) → APPROVE
- `case_conditional.json` — Apex Steel (borderline, CMR 6, DPD 45, ITC excess) → CONDITIONAL
- `case_reject.json` — Greenfield Pharma (CMR 9, DPD 120, cycle detected, criminal cases) → HARD REJECT

To load via API:
```bash
curl -X POST http://localhost:8000/api/cases/ \
  -H "Content-Type: application/json" \
  -d @demo/seed/case_approve.json
```

---

## Table of contents

1. [Scope & Assumptions](#scope--assumptions)
2. [Core Operating Imperatives](#core-operating-imperatives)
3. [Active Context Compression (Focus loop)](#active-context-compression-focus-loop)
4. [Infrastructure Initialization Protocol (bootstrap)](#infrastructure-initialization-protocol-bootstrap)

   * Hardware & container runtime
   * Python environment tooling
5. [Component Implementation Directives](#component-implementation-directives)

   * Visual ingestion (GLM-OCR)
   * Cognitive inference (DeepSeek-R1-Distill-Llama-8B)
   * Distributed orchestration (Agent Framework)
   * Stealth web extraction (Firecrawl-Simple)
   * Entity resolution & data processing (DuckDB, Crocodile)
6. [Domain Logic / Credit Appraisal Imperatives](#domain-logic--credit-appraisal-imperatives)
7. [Deployment & Resource Bounding Guidelines](#deployment--resource-bounding-guidelines)
8. [Appendix — Example scripts, snippets, and templates](#appendix---example-scripts-snippets-and-templates)

---

## Scope & Assumptions

* Single host constraints: **24 GB VRAM GPU**, **64 GB DDR5 RAM**. All services must respect these limits.
* Host environment: **Windows Subsystem for Linux (WSL2)** running **Ubuntu 22.04+**. Work inside a **new empty directory** in WSL for the entire project.
* Local-only, open-source models and components. No cloud dependencies or external managed services that require billing.
* Goal: robust, repeatable, reproducible build and deployment (scripts + Docker + local artifacts). Fault tolerance and dependency isolation are mandatory.
* You are permitted to pivot implementations where compilation or compatibility problems arise, but always prefer local open-source implementations and document the pivot decision clearly.

---

## Core Operating Imperatives

* Absolute stability, deterministic dependency management, and runnable artifacts are **required**. Fail early and document pivots.
* Everything required to reproduce the environment must be scripted (bash + Dockerfiles + docker-compose + pyenv local files). No manual, undocumented steps.
* Where version conflicts exist, prefer multiple isolated Python runtimes via `pyenv` + `pyenv-virtualenv` (or `venv`) — *do not* use the global system Python.

---

## Active Context Compression (Focus loop)

For every substantial sub-task, follow this loop and persist a short summary into the repo (e.g., `knowledge_blocks/`):

1. **Start Focus:** Create a checkpoint heading (example: `FOCUS: PyReason logic graph construction`) and commit it to a local `focus_log.md`.
2. **Explore:** Implement, run, and debug. Keep noisy logs local to the task workspace.
3. **Consolidate & Withdraw:** Produce a 3–6 line summary describing:

   * what was attempted,
   * key facts discovered (versions, compile errors),
   * final outcome and next action (pivot or complete).
     Append this summary to a persistent `knowledge_block.md` and move raw logs to `logs/` with a single-line pointer in the knowledge block.

This ensures the working context remains compact and machine-tractable across long sessions.

---

## Infrastructure Initialization Protocol (bootstrap)

### Hardware & container runtimes — required actions

1. Update APT and install prerequisites:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release apt-transport-https
```

2. Install Docker and docker-compose plugin (canonical steps):

```bash
# Add Docker repo
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

3. Install NVIDIA container toolkit and configure Docker to expose GPU:

```bash
# Add NVIDIA package repos
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update
sudo apt install -y nvidia-container-toolkit
# Configure the Docker daemon (example: nvidia-ctk). If your distro provides nvidia-ctk:
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

> **Note:** If `nvidia-ctk` is unavailable, follow NVIDIA's official instructions for `nvidia-container-toolkit` and configure `/etc/docker/daemon.json` with the proper runtime settings. Always confirm `docker run --gpus all nvidia/cuda:11.0-base nvidia-smi` succeeds.

---

### Python environment landmines & recommendations

* **Do NOT** use global Python. Use `pyenv` + `pyenv-virtualenv` (recommended) or `pyenv` + native `venv`.
* Example installs:

```bash
# Install pyenv dependencies (Ubuntu)
sudo apt install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
  libreadline-dev libsqlite3-dev llvm libncurses5-dev libncursesw5-dev \
  xz-utils tk-dev libffi-dev liblzma-dev

# Install pyenv + pyenv-virtualenv (follow pyenv docs)
curl https://pyenv.run | bash
# Then add pyenv init to shell rc and restart shell
# Example: ~/.bashrc additions (handled in a bootstrap script)
```

* **Critical versions:**

  * **PyReason & IBM LNN layers**: pin to **Python 3.10** (Numba compatibility issues exist with 3.11/3.12). Create a pyenv environment `3.10.x` for these modules.
  * **GLM-OCR** service: the spec calls for Python 3.12 — create a separate env for it. Use isolated virtualenvs per service (one env per service).

* Sample pyenv commands:

```bash
pyenv install 3.10.13
pyenv install 3.12.0
pyenv virtualenv 3.10.13 py310-pyreason
pyenv virtualenv 3.12.0 py312-glmocr
# In each component directory, put a .python-version file with the virtualenv name
```

---

## Component Implementation Directives

### 1) Visual Ingestion — `GLM-OCR`

* **Goal:** Parse chaotic Indian PDFs → structured Markdown.
* **Environment:** **Python 3.12** dedicated virtualenv.
* **Dependencies:** Install bleeding-edge `transformers` from source:

```bash
pip install git+https://github.com/huggingface/transformers.git
```

* **Runtime engine:** Prefer **vLLM** for batched, high-throughput inference. Launch server with suggested flags (example):

```bash
vllm_server --model /path/to/glm-ocr-model --speculative-config.method mtp
```

* **Fallback:** If vLLM fails (CUDA/Wsl compilation errors), pivot to **SGLang** server:

```bash
python -m sglang.launch_server
```

* **Notes / TODOs:** Pin CUDA toolkit and PyTorch/CUDA builds that are known to work inside WSL + your GPU driver. Document exact working combinations in `knowledge_blocks/glm_ocr.md`.

---

### 2) Cognitive Inference — `DeepSeek-R1-Distill-Llama-8B`

* **Model:** Use quantized **Q4_K_M GGUF** variant (Hugging Face) to fit VRAM constraints. **Do not** attempt FP16 weight loads.
* **Load engine:** Use a GPU-accelerated build of `llama.cpp` (or a community fork that supports CUDA offloading). Compile from source and use `--gpu-layers` to offload layers to GPU.
* **Memory planning:** After GLM-OCR allocation, allocate remaining VRAM to the model context. The spec requests a **128k** context — evaluate feasibility; **context size is a hard VRAM consumer**. Tune `--ctx-size` conservatively, measure memory, iterate.
* **Important:** The system expects `think` / `</think>` tokens preserved in outputs. Ensure any postprocessing scripts or tokenizers do not strip these tags.
* **Suggested compile snippet (example):**

```bash
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
# Example make command — use the repo's CUDA guide or a GPU-enabled fork
make clean && make
```

* **Runtime example:** (illustrative)

```bash
./main -m /models/deepseek-q4.gguf --gpu-layers 16 --ctx-size 131072
```

---

### 3) Distributed Orchestration — Microsoft Agent Framework

* **Install:** `pip install agent-framework --pre` (use the pre-release if required).
* **Pattern:** Implement a **Durable Agent** pattern to persist agent state, memory, and tool ledgers across restarts.
* **Tool binding:** Wrap external interfaces (DuckDB queries, Firecrawl endpoints) as **tools** using MCP-style JSON-RPC clients to keep tool calls compact and standardized.
* **Persistence:** Use local durable storage (SQLite/Mongo/Flat-files) depending on agent-framework recommendations; ensure agents write checkpoints frequently.

---

### 4) Stealth Web Extraction — `firecrawl-simple`

* **Goal:** stealthily collect public legal/promoter data for credit decision signals.
* **Deployment:** Clone the fork and deploy via Docker Compose. Remove extraneous billing or heavy AI features.
* **Resource bounding:** Enforce memory limits in `docker-compose.yml` (example: Playwright worker `mem_limit: 4G`) to prevent runaway RAM usage.
* **Proxying / IP mitigation:** Configure proxy rotation / per-container proxies in `.env` to lower Cloudflare triggering probability. Document proxy strategy and legal boundaries for scraping in `LEGAL.md`.

---

### 5) Entity Resolution & Data Processing

* **Lakehouse:** Use **DuckDB** for analytics directly over CSV/Parquet with Arrow zero-copy.
* **Linking:** Use **Crocodile** (`pip install crocodile-linker`) for entity matching with async workers and local caching (MongoDB) to avoid repeated LLM calls for exact matches.
* **Workflow:** Ingest bank statements / GSTR files → DuckDB transforms → Crocodile performs entity resolution → results are materialized to Parquet and indexed.

---

## Domain Logic Imperatives for Credit Appraisal

Encode strict, auditable domain rules in the Neuro-Symbolic stack (IBM LNN + PyReason). Required checks include, but are not limited to:

1. **GST Reconciliation (GSTR-2A vs GSTR-3B)**

   * Cross-validate Input Tax Credit (ITC) on GSTR-3B vs what appears in supplier-populated GSTR-2A. Significant excess ITC in 3B → **red flag**.
   * Cross-check declared sales in GSTR-1/3B against cash-flow velocity from bank statements; large mismatches should flag circular trading and route evidence to a FLAG GNN for multi-hop relationship reasoning.

2. **CIBIL Commercial Report Interpretation**

   * Extract `CIBIL MSME Rank (CMR)` and `Credit Profile Summary`.
   * Derogatories: dishonoured cheques, DPD > thresholds, or assets moving to "Non-Standard" → **hard constraints** in LNN. This forces CAM adjustments (raise risk premium or reject) and must include explicit evidence in the Neuro-Symbolic trace.

3. **CAM (Credit Appraisal Memo) Generation**

   * Use `python-docx-template` to populate a Word template with structured Jinja2-like tags:

```jinja
{{ borrower_name }}
{% for risk in risk_factors %}
 - {{ risk.description }}
{% endfor %}
```

* The orchestration agent must feed an evidence-backed data dictionary into this template. Include a serialized Neuro-Symbolic trace appendix with citations to original artifacts (bank statements, GST returns, CIBIL excerpts).

---

## Deployment & Resource Bounding Guidelines

* **Container memory limits** — set strict `mem_limit` and CPU quotas for all worker containers. Keep heavy inference processes isolated (GPU-only containers) and ensure they do not spawn unbounded child processes.
* **Disk & data retention:** store raw sensitive input files offline under `storage/raw/` and keep processed artifacts in `storage/processed/`. Apply rotation policies and a `retention_policy.md`.
* **Monitoring:** instrument resource usage (GPU memory, container memory) and log failures to `logs/monitoring/`. If memory pressure crosses thresholds, agents must gracefully degrade context size rather than crash.

---

## Appendix — Example scripts, snippets, and templates

### `bootstrap.sh` (example skeleton)

```bash
#!/usr/bin/env bash
set -euo pipefail

# run from project root
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release apt-transport-https build-essential \
  libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev llvm libncurses5-dev \
  libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev

# Docker + NVIDIA toolkit steps - see main doc for full commands (may require root)
# pyenv bootstrap (user-level)
curl https://pyenv.run | bash

echo "Bootstrap complete. Next: install pyenv, add the shims to your shell rc, and run ./setup_pyenv.sh"
```

### `docker-compose` memory bounding example

```yaml
version: '3.8'
services:
  playwright_worker:
    image: my/playwright-worker:latest
    mem_limit: 4g
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 4G
    environment:
      - PROXY=${PLAYWRIGHT_PROXY}
```

### `pyenv` and virtualenv example

```bash
pyenv install 3.10.13
pyenv virtualenv 3.10.13 py310-pyreason
# In GLM-OCR dir:
pyenv install 3.12.0
pyenv virtualenv 3.12.0 py312-glmocr
```

### `docx` template example (Jinja-like)

```jinja
Credit Appraisal Memo

Borrower: {{ borrower_name }}
Loan Amount Requested: {{ loan_amount }}

Risks:
{% for r in risk_factors %}
- {{ r.severity }}: {{ r.summary }}
{% endfor %}
```

---

## Final notes & recommended next steps (actionable)

1. Create a `repo_root` folder inside WSL and commit this `CLAUDE.md` as the top-level blueprint.
2. Add a `scripts/` directory and populate with `bootstrap.sh`, `setup_pyenv.sh`, `build_llama.sh`, and `deploy_compose.sh`. Make all scripts idempotent where possible.
3. Implement **Focus loop** habit immediately: create `knowledge_blocks/` and a `focus_log.md` file and enforce the 3-step summary pattern after every subtask.
4. Start by validating the GPU passthrough (run `docker run --gpus all nvidia/cuda:11.0-base nvidia-smi`) and then install `pyenv` and create the two required Python environments (3.10 for PyReason; 3.12 for GLM-OCR). Document exact successful combinations of CUDA, PyTorch, and drivers in `knowledge_blocks/compat_matrix.md`.
5. Iterate on quantized model selection (Q4_K_M) and confirm VRAM usage in a small smoke test before committing to a full 128k context attempt.

---
