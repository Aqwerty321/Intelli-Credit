# VISION.md — The Intelli-Credit Zero-Trust Edge Architecture

> **Mission:** Replace weeks of manual corporate credit processing with a fully local, auditable, open-source decisioning engine that automatically generates a Comprehensive Credit Appraisal Memo (CAM) while enforcing regulatory auditability and strict data sovereignty.
> This version is updated after reviewing the hackathon Problem Statement and research files in `problem_statement_and_initial_research`. 

---

## Key entities and projects (each referenced once)

* Reserve Bank of India
* Databricks
* DuckDB
* LanceDB
* Apache Iceberg
* GLM-OCR
* DeepSeek-R1
* Llama-3
* LoRA
* Crocodile
* FLAG
* Microsoft Agent Framework
* Firecrawl
* PyReason
* IBM Logical Neural Networks

> Subsequent sections use plain names for readability.

---

## Executive summary (short)

* Build a 100% open-source, locally hosted Credit Decisioning Engine that:

  * ingests messy Indian corporate documents (GST returns, bank statements, CIBIL reports, annual reports),
  * autonomously collects secondary research,
  * reasons with a quantized LLM plus Neuro-Symbolic constraints,
  * generates a fully traceable CAM with linked provenance.
* Hardware envelope: **single workstation** with **24 GB VRAM GPU** and **64 GB RAM**. All design choices are constrained by this budget.
* This doc updates prior architecture to align tightly with the hackathon Problem Statement and initial research artifacts stored in the repo. 

---

## Hardware feasibility & conservative resource allocation (starting targets)

> Validate these targets with profiling early; adjust where tests show actual footprints differ.

| Component         |                  Stack (example) |               VRAM |      System RAM | Purpose / Notes                           |
| ----------------- | -------------------------------: | -----------------: | --------------: | ----------------------------------------- |
| Host / Containers |                    WSL2 + Docker |               0 GB |           ~4 GB | Container runtime, networking             |
| Data substrate    |                 DuckDB + LanceDB |               0 GB |          ~16 GB | Zero-copy analytics & vector SQL          |
| Visual ingestion  |                   GLM-OCR (0.9B) | ~3.0 GB (bfloat16) |         ~2.0 GB | PDF → structured Markdown                 |
| Cognitive core    | DeepSeek-R1 Distill (8B, Q4_K_M) |            ~6.0 GB |         ~4.0 GB | Primary reasoning engine (quantized)      |
| Context memory    |        KV Cache / PagedAttention |           ~14.9 GB |            0 GB | Large context windows kept VRAM-resident  |
| Domain adapters   |                    LoRA matrices |     ~0.1 GB active | ~1.0 GB passive | Task specialization via dynamic swap      |
| Graph analytics   |                       FLAG (PyG) |               0 GB |        ~10.0 GB | CPU graph computations (PageRank, motifs) |
| Neuro-Symbolic    |               PyReason + IBM LNN |               0 GB |         ~8.0 GB | Deterministic regulatory logic            |
| Web extraction    |                 Firecrawl-Simple |               0 GB |         ~4.0 GB | JS rendering, stealth crawling            |
| Headroom          |                                — |                  — | ~15 GB reserved | Safety buffer for spikes                  |

---

## Architectural principles

1. **Local-first, open-source only.** No proprietary cloud services for core processing; all artifacts and models remain on the host.
2. **Zero-trust & auditability.** Every automated decision includes provenance (file ID, page, byte offsets, extraction method, timestamp). Store provenance in the lakehouse.
3. **Resource partitioning.** VRAM prioritized for model weights + KV cache; heavyweight graph and symbolic workloads remain on CPU/RAM.
4. **Fault-tolerant pivots allowed.** If a component fails to compile or run in WSL, implement and document a tested fallback (e.g., SGLang for OCR inference; Tesseract fallback for low-confidence extractions).
5. **Automated reproducibility.** Everything scripted and idempotent (bootstrap scripts, Dockerfiles, docker-compose, pyenv env files).

---

## Pillar I — Composable local Lakehouse (replace proprietary lakehouse)

**Why:** avoid JVM bloat and vendor lock while keeping SQL + semantic retrieval in one plane.

* **DuckDB**: primary embedded analytics engine for zero-copy Arrow operations and fast vectorized SQL.
* **Apache Iceberg**: table format for atomic commits, time travel, and concurrent agent-safe writes.
* **LanceDB + Lance↔DuckDB extension**: store vector embeddings and run similarity joins directly in SQL.
* **Workflow advantage:** semantic retrieval (embeddings) becomes a SQL primitive — agents can join litigation embeddings with transactional filters without network hops.

**Operational notes**

* Enforce small, frequent commits; store raw files in `storage/raw/` and processed artifacts in `storage/processed/`.
* Maintain `knowledge_blocks/compat_matrix.md` documenting working combinations of CUDA, drivers, and library versions.

---

## Pillar II — Visual Document Understanding (GLM-OCR + preprocessing)

**Problem:** Indian corporate PDFs are noisy and varied; a single-pass OCR rarely suffices.

**Pipeline (must implement):**

1. **Raw extraction:** use `pdfimages`/poppler to extract page images.
2. **Image preprocessing:** deskew, denoise, adaptive thresholding, DPI normalize (target 300 DPI). Use OpenCV / pyvips for fast batch processing.
3. **Table detection:** run a table detector (Camelot / Tabula as fallbacks). Mark table regions and pass them to GLM-OCR with cell coordinate metadata.
4. **GLM-OCR inference:** run model at bfloat16 if supported; provide locale and numeric format hints (e.g., `en-IN`, lakhs/crores separators).
5. **Postprocessing & validation:** apply regex-based checks for critical fields (GSTIN, PAN, invoice totals). If OCR and fallback disagree beyond threshold, flag for manual review.

**Fallbacks**

* Tesseract + rule-based parsers for fields with low confidence.
* If vLLM/vGPU inference fails in WSL, pivot to SGLang server fallback.

**Outputs**

* Structured Markdown frontmatter + CSV/Parquet fragments for tables, with provenance metadata.

---

## Pillar III — Cognitive Core (DeepSeek-Distill + LoRA adapters)

**Design**

* Use a distilled LLM footprint (DeepSeek-R1 → Llama family distilled 8B) quantized to GGUF Q4_K_M to fit VRAM.
* Prioritize loading weights (~6 GB) and reserving the remaining VRAM for a KV cache enabling large contexts (target up to 128k where feasible).
* Use LoRA adapters for specialized legal/financial expertise; store many small LoRA files on disk and dynamically swap active adapters into GPU VRAM at inference time.

**Engineering practices**

* Implement chunking & chain-of-thought preservation: annotate chunks with provenance and ensure `<think>...</think>` tags survive tokenization and postprocessing.
* Smoke test utilities: `scripts/profile_deepseek.sh` to measure VRAM and latency with different `--ctx-size` settings.

**Tradeoffs**

* Quantization reduces absolute precision — include evaluation harness to compare downstream scoring stability vs a higher-precision baseline on a small sampled CAM set.

---

## Pillar IV — Graph-theoretic fraud detection (FLAG)

**Problem:** circular trading and fraud are topological, not row-wise anomalies.

**Approach**

* Construct transaction graphs from DuckDB; compute centrality and motifs in RAM using PyTorch Geometric where needed.
* Generate node features from DeepSeek embeddings (GPU) and run FLAG graph topology algorithms (semantic neighbor sampling + jump-attentive GNN) to detect camouflage.
* Keep heavy centrality and adjacency computations in CPU/RAM; reserve GPU for semantic embedding generation only.

**Outputs**

* Suspicious subgraph reports with provenance and a risk score that becomes input to Neuro-Symbolic rules.

---

## Pillar V — Swarm intelligence & stealth web extraction

**Components**

* Durable agent orchestration via Microsoft Agent Framework (MAF) to persist agent state, tool ledgers, and conversation context into DuckDB.
* Firecrawl-Simple (self-hosted Docker) for JS rendering and stealth crawling with strict container resource limits.

**Agent behavior**

* Crawl policies respect `LEGAL.md` (per-domain rate limits, robots.txt, opt-out logic).
* Agents persist crawl provenance for every extracted item (URL, crawl timestamp, DOM snippet, rendered image, extraction confidence).

**Acceptance requirement**

* Research agents must surface at least one corroborated external evidence item not present in the initial dataset for each tested company in `tests/research_depth/`.

---

## Pillar VI — Neuro-Symbolic Decisioning (PyReason + IBM LNN)

**Why:** purely generative outputs are insufficient for regulatory auditability.

**Flow**

1. LLM drafts candidate assessments and CAM text.
2. PyReason ingests parsed facts, FLAG outputs, and LLM proposals to produce deterministic inferences with provenance.
3. IBM LNN applies weighted logic constraints and enforces hard regulatory thresholds (GST mismatches, DPD thresholds, dishonoured cheque counts). Violations adjust outcomes and produce penalized loss artifacts.
4. Final CAM includes a Neuro-Symbolic trace appendix linking decisions to raw artifacts.

**Rule management**

* Store rules as `rules/<NNNN>-slug.yml` with: rule id, threshold, severity, human rationale, and tests. Keep them source controlled.

---

## Data pipeline (high level)

1. Ingest raw file → preprocess → GLM-OCR → structured Markdown & table fragments (Parquet).
2. Load structured outputs into DuckDB + LanceDB (embeddings) with Iceberg table semantics for atomic commits.
3. Run entity resolution via Crocodile → normalized entities.
4. Construct graphs from transactional joins → FLAG analysis.
5. LLM + LoRA produce draft CAM and candidate rationales.
6. PyReason + IBM LNN finalize decisions; generate DOCX via `python-docx-template` and store in `storage/processed/`.

---

## Acceptance tests & evaluation harness (must implement)

Create `acceptance/` with machine-runnable tests producing JSON reports in `reports/acceptance/`:

1. **Extraction accuracy**

   * Field-level precision/recall for GSTIN, invoice amount, PAN, dates on `tests/extraction_smoke/`. Baseline target: **> 90%** on smoke dataset.
2. **Research depth**

   * Agent must find ≥1 corroborated external evidence item not in initial research files per sample company. Measure Hits@10 and time-to-first-relevant.
3. **Explainability coverage**

   * For each CAM, compute % recommendations with at least one deterministic PyReason/LNN trace. Targets: **100%** for hard rejects; **> 90%** for risk adjustments.
4. **India context sensitivity**

   * GST, GSTR mismatch and CIBIL parsing unit tests.
5. **Resource / profiling**

   * VRAM smoke test for concurrent GLM-OCR + DeepSeek; confirm headroom remains.
6. **Mem limit enforcement**

   * Confirm Docker mem limits prevent OOM of other services.

Provide `scripts/run_acceptance.sh` to run the full suite and output JSON.

---

## Security, privacy, governance

* **Zero-trust:** data never leaves the host unless explicitly permitted; external network calls routed via auditable proxies.
* **Access controls:** containerization, least privilege, and optional disk encryption.
* **Audit trails:** every agent tool call, model inference, and rule firing writes a provenance record to DuckDB.
* **Data retention:** policies in `LEGAL.md` and `retention_policy.md`.

---

## Practical next steps (actionable)

1. Commit `VISION.md` and create directories: `rules/`, `knowledge_blocks/`, `storage/{raw,processed}`, `acceptance/`, `tests/`.
2. Implement preprocessing + GLM-OCR smoke: one noisy multi-page PDF from `problem_statement_and_initial_research` → structured Markdown → ingest into DuckDB; capture metrics. 
3. Implement `scripts/profile_deepseek.sh` and run VRAM profiling for Q4 model with small contexts.
4. Implement first 10 PyReason rules in `rules/` (GST mismatch, DPD thresholds, dishonour counts, circular trading indicators) and unit tests.
5. Create `LEGAL.md` that documents crawling policies and data governance constraints.

---

## Appendix — repo artifacts to add now

* `VISION.md` (this file)
* `CLAUDE.md` (existing operative directives)
* `scripts/bootstrap.sh`, `scripts/setup_pyenv.sh`, `scripts/run_acceptance.sh`, `scripts/profile_deepseek.sh` (skeletons)
* `acceptance/` skeleton with subfolders: `extraction_smoke/`, `research_depth/`, `cam/`, `entity_resolution/`
* `rules/` starter YAMLs and `knowledge_blocks/compat_matrix.md` for tested environment combos.
* `LEGAL.md` (crawler policy + data governance)

---

## Implementation status (current build)

> This section documents what has been built and validated as of the current commit.

### What is running

| Layer | Component | Status |
|---|---|---|
| Document ingestion | PaddleOCR-VL (Python 3.12 venv) | ✅ Working — F1=1.0 on smoke set |
| Cognitive core | DeepSeek-R1 8B Q8 via Ollama | ✅ Running at `http://172.23.112.1:11434` |
| Rule engine | `services/reasoning/rule_engine.py` v2 | ✅ 22/22 unit tests PASS |
| Rules | `rules/0001–0010 *.yml` — all at schema v2 | ✅ Validated, no namespaced keys |
| Research agent | `services/agents/research_agent.py` | ✅ Domain blocklist, tiers, entity gating, caching |
| Web extraction | SearXNG Docker at `localhost:8888` | ✅ Running |
| Data substrate | DuckDB 8-table lakehouse | ✅ Operational |
| API server | FastAPI at `localhost:8000` | ✅ 13 routes, SSE streaming |
| Frontend | Vite + React 18 + Tailwind CSS | ✅ Builds clean (37 modules) |
| Test suite | pytest — 36 tests | ✅ 36/36 PASS |

### Rule engine v2 schema

All rules stored in `rules/` use canonical v2 schema:
- `version: "2.0"` at top level
- `direction: above|below` on the condition block (default: `above`)
- `risk_adjustment` lives on **each threshold object**, not on the `action` block
- `_eval_threshold()` walks thresholds ascending for `above` (highest crossed wins) and descending for `below` (lowest crossed wins)
- Rule firings include `schema_version: "v2"` and `missing_data_flags` in their serialized output
- Template strings use `_safe_format()` which substitutes `[N/A]` for any missing keys instead of raising `KeyError`

**Forbidden (v2 invariant):** never use namespaced keys like `risk_adjustment_high:` inside the `action:` block. These silently return 0.0.

### Research agent precision controls

- `DOMAIN_TIERS`: 25-entry dict mapping domain → confidence score (0.40–0.95). RBI/SEBI/MCA at top; dictionaries/Reddit at bottom.
- `DOMAIN_BLOCKLIST`: 26-entry set — results from these domains are dropped before scoring.
- `_entity_matches()`: requires the exact company name phrase OR 2+ significant words (>4 chars) from the name both appear in the result text. Prevents false positives like "steel cut oats recipe" matching "Apex Steel Ltd".
- File caching: `storage/cache/research/<company>_research.json` — checked before hitting SearXNG.
- Every finding includes `sentiment_score` (float) and `domain_confidence` (float) fields.

### Full-stack UI

- **Backend**: `app/main.py` + `app/api/cases.py` (CRUD) + `app/api/run.py` (SSE streaming)
- **Frontend**: `frontend/src/components/` — `CaseList`, `CaseCreate`, `CaseDetail`
- `CaseDetail` has 5 tabs: Documents → Run → Evidence → Trace → CAM
- Run tab streams pipeline progress via SSE (Server-Sent Events) — no polling

### Demo dataset

`demo/seed/` contains three representative cases for demo/smoke-testing:

| File | Company | Expected | Key signals |
|---|---|---|---|
| `case_approve.json` | Sunrise Textiles | APPROVE | CMR=3, DPD=0, collateral=1.6x |
| `case_conditional.json` | Apex Steel | CONDITIONAL | CMR=6, DPD=45, ITC excess=33% |
| `case_reject.json` | Greenfield Pharma | HARD REJECT | CMR=9, DPD=120, cycle detected, 2 criminal cases |

---
