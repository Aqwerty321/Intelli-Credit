# Intelli-Credit

> **AI-powered credit appraisal engine** — a fully local, zero-cloud decisioning system for MSME lending, combining neuro-symbolic rule inference, multi-agent research, GNN-based fraud detection, and a professional React UI.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture Overview](#architecture-overview)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Quick Start](#quick-start)
6. [Backend API Reference](#backend-api-reference)
7. [Frontend Pages & Components](#frontend-pages--components)
8. [Intelligence Pipeline](#intelligence-pipeline)
9. [Rule Engine v2](#rule-engine-v2)
10. [Graph & GNN Intelligence](#graph--gnn-intelligence)
11. [Research Agent System](#research-agent-system)
12. [CAM Generation (Markdown + PDF)](#cam-generation-markdown--pdf)
13. [Demo Intelligence Pack](#demo-intelligence-pack)
14. [Test Suite](#test-suite)
15. [Configuration & Environment](#configuration--environment)
16. [Scripts Reference](#scripts-reference)
17. [Storage Layout](#storage-layout)

---

## What It Does

Intelli-Credit automates the **Credit Appraisal Memo (CAM)** workflow for MSME/SME lending:

1. **Ingest** messy borrower documents (PDF, Markdown, structured JSON) via a drag-and-drop UI.
2. **Extract & analyse** financial facts: GST reconciliation, CIBIL CMR, DPD history, collateral, capacity utilisation.
3. **Research** the borrower autonomously using a multi-agent LLM pipeline backed by SearXNG, scoring and de-duplicating web evidence.
4. **Build a transaction graph**, run GNN classification to identify fraud topologies (circular trading, ring networks, star-seller schemes), and detect suspicious cycles.
5. **Apply a neuro-symbolic rule engine** (10 YAML rules, schema v2) to fire deterministic risk adjustments backed by full audit traces.
6. **Synthesise** all signals into a scored verdict (`APPROVE` / `CONDITIONAL` / `REJECT`) with an evidence-backed CAM in Markdown and PDF.
7. **Present** the full decision in a React dashboard — risk gauge, waterfall chart, D3 force graph, ONNX GNN playground, evidence scatter, and side-by-side case comparison.

Everything runs **locally on a single GPU workstation** — no cloud APIs, no billing, no data leaving the machine.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  React + Vite Frontend  (http://localhost:5173)                 │
│  Dashboard · CaseList · CaseDetail · CaseCompare               │
│  D3 ForceGraph · Recharts · ONNX GNN Playground                │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST + SSE (Server-Sent Events)
┌────────────────────────▼────────────────────────────────────────┐
│  FastAPI Backend  (http://localhost:8000)                       │
│  /api/cases   /api/run   /api/health                           │
└──┬─────────────┬────────────┬──────────────┬────────────────────┘
   │             │            │              │
   ▼             ▼            ▼              ▼
Ingestor    Lakehouse    Rule Engine    Agent Orchestrator
(PDF/MD/    (DuckDB)     (YAML v2,      ├── ResearchRouterAgent
 JSON OCR)              PyReason FB)    ├── ResearchAgent (SearXNG)
                                        ├── EvidenceJudgeAgent
   ▼                                    ├── ClaimGraph
Graph Builder                           └── CounterfactualChallenger
(NetworkX)
   │
   ▼
GNN Intelligence           CAM Generator
(PyTorch Geometric)        (Markdown + ReportLab PDF)
Cycle Detection
```

The pipeline is fully **event-driven over SSE** — the frontend receives live progress events (`research_plan_ready`, `evidence_scored`, `claim_graph_ready`, `counterfactual_ready`, `complete`) as each agent finishes.

---

## Tech Stack

### Backend

| Component | Technology |
|-----------|-----------|
| API server | FastAPI 0.135 + Uvicorn 0.41 |
| Streaming | SSE via `sse-starlette` |
| LLM inference | Ollama (`sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0`) |
| Light agent LLM | Ollama `qwen2.5:3b` (Router / Judge / ClaimGraph) |
| Web search | SearXNG (Docker, `localhost:8888`) |
| Analytics / ETL | DuckDB 1.4.4 |
| Graph analytics | NetworkX 3.6 + PyTorch Geometric |
| Rule engine | Custom YAML DSL + PyReason fallback |
| PDF generation | ReportLab 4.4.10 |
| OCR | PyMuPDF 1.27 + GLM-OCR (optional) |
| Entity resolution | RapidFuzz 3.14 |
| Python | 3.12 (`.venv`) |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 18.3 + Vite 5.4 |
| Routing | React Router DOM 6.28 |
| Styling | Tailwind CSS 3.4 |
| Charts | Recharts 3.8 (pie, bar, radar, scatter, waterfall) |
| Graph viz | D3.js 7.9 (force-directed layout) |
| Browser ML | ONNX Runtime Web 1.24 (WASM, runs GNN in-browser) |
| Tests | Vitest + happy-dom |
| E2E tests | Playwright |

---

## Project Structure

```
Intelli-Credit/
├── app/
│   ├── main.py                  # FastAPI app, CORS, static serving
│   └── api/
│       ├── cases.py             # All case CRUD + stats + compare + PDF CAM endpoints
│       └── run.py               # SSE appraisal pipeline endpoint
│
├── services/
│   ├── pipeline.py              # End-to-end pipeline orchestrator
│   ├── agents/
│   │   ├── orchestrator.py      # Multi-agent coordinator (tool-based)
│   │   ├── research_agent.py    # SearXNG researcher, noise/stale hardening
│   │   ├── research_router.py   # LLM search planner with deterministic fallback
│   │   ├── evidence_judge.py    # Composite evidence scorer (precision@10)
│   │   ├── claim_graph.py       # Claim extraction + contradiction detection
│   │   └── counterfactual.py   # What-if scenario generator
│   ├── cam/
│   │   ├── generator.py         # Markdown CAM generation
│   │   └── pdf_generator.py     # ReportLab PDF CAM (multi-page, styled)
│   ├── graph/
│   │   ├── builder.py           # Transaction graph construction (NetworkX)
│   │   └── intelligence.py      # GNN + cycle detection + entity scoring
│   ├── reasoning/
│   │   └── rule_engine.py       # YAML rule loader + deterministic inference (v2)
│   ├── ingestor/
│   │   ├── preprocess.py        # Document normalisation pipeline
│   │   ├── validator.py         # Regex-based fact extraction from MD/PDF
│   │   ├── provenance.py        # Source tracking
│   │   └── glm_ocr.py           # GLM-OCR integration (optional)
│   ├── lakehouse/
│   │   └── db.py                # DuckDB ETL (transactions, GST, CIBIL)
│   ├── entity_resolution/
│   │   └── resolver.py          # RapidFuzz entity matching
│   └── cognitive/
│       └── engine.py            # DeepSeek-R1 reasoning wrapper
│
├── rules/                       # 10 YAML rule files (schema v2)
│   ├── 0001-gst-itc-mismatch.yml
│   ├── 0002-circular-trading-indicator.yml
│   ├── 0003-dpd-threshold.yml
│   ├── 0004-dishonoured-cheques.yml
│   ├── 0005-cibil-cmr-threshold.yml
│   ├── 0006-revenue-inflation.yml
│   ├── 0007-promoter-litigation.yml
│   ├── 0008-capacity-utilization.yml
│   ├── 0009-sector-headwind.yml
│   └── 0010-collateral-coverage.yml
│
├── frontend/
│   ├── public/
│   │   └── models/              # ONNX model + WASM runtime (gitignored binaries)
│   │       ├── demo_graph_gnn.onnx
│   │       ├── demo_graph_gnn_meta.json
│   │       └── ort-wasm-simd-threaded.*.{mjs,wasm}   ← copied by start.sh
│   └── src/
│       ├── App.jsx              # Router — /, /cases, /cases/new, /cases/compare, /cases/:id
│       ├── components/
│       │   ├── AppShell.jsx     # Sidebar nav, health badge, case list
│       │   ├── Dashboard.jsx    # Portfolio KPIs, charts, activity timeline
│       │   ├── CaseList.jsx     # Sortable case table with per-row delete
│       │   ├── CaseCreate.jsx   # New case form
│       │   ├── CaseDetail.jsx   # Full case view with tabbed panels
│       │   ├── CaseCompare.jsx  # Side-by-side comparison for 2–5 cases
│       │   ├── ConfirmModal.jsx # Reusable danger/safe confirmation modal
│       │   ├── charts/
│       │   │   ├── RiskGauge.jsx         # Donut arc gauge (% label centred)
│       │   │   ├── RiskWaterfall.jsx     # Rule-firing waterfall bar chart
│       │   │   ├── ClassRadar.jsx        # GNN entity class radar
│       │   │   ├── CounterfactualBar.jsx # What-if delta bar chart
│       │   │   ├── EvidenceScatter.jsx   # Evidence confidence × relevance scatter
│       │   │   ├── ForceGraph.jsx        # D3 force-directed transaction graph
│       │   │   └── GraphPlayground.jsx   # Interactive ONNX GNN inference UI
│       │   └── panels/
│       │       ├── KPIStrip.jsx          # 5-tile KPI row (verdict, risk, rules, evidence, graph)
│       │       ├── CaseHeader.jsx        # Case title + verdict + risk badge
│       │       ├── RunPanel.jsx          # SSE live log + run trigger
│       │       ├── TracePanel.jsx        # Rule firings + graph trace breakdown
│       │       ├── EvidencePanel.jsx     # Research findings list
│       │       ├── GraphPanel.jsx        # D3 graph + GNN results
│       │       ├── JudgePanel.jsx        # Evidence quality, claim graph, counterfactuals, search plan
│       │       ├── CAMPanel.jsx          # Markdown preview + PDF/MD download buttons
│       │       ├── NotesPanel.jsx        # Officer notes (CRUD, tags, pinned, search)
│       │       ├── DocumentsPanel.jsx    # Uploaded document list
│       │       └── PipelineTimeline.jsx  # Step-by-step pipeline progress
│       ├── services/
│       │   ├── api.js           # Centralised async API client (all endpoints)
│       │   └── gnn.js           # ONNX Runtime Web GNN inference
│       └── utils/
│           └── formatters.js    # Shared formatting helpers
│
├── demo/
│   └── intelligence_cases/      # 5-case deterministic demo pack
│       ├── manifest.json
│       ├── approve/             # Sunrise Textiles — APPROVE (risk 0.30)
│       ├── conditional/         # Apex Steel — CONDITIONAL (risk 0.65)
│       └── reject/              # Greenfield Pharma — REJECT (risk 1.0 hard)
│
├── tests/
│   ├── integration/             # 9 integration test modules
│   └── unit/                    # Unit tests for rule engine, graph, counterfactuals
│
├── scripts/
│   ├── start.sh                 # One-command startup
│   ├── run_acceptance.sh        # Run full test suite
│   ├── judge_pack.sh            # Tests + showdown + scorecard
│   ├── demo_intelligence_pack.py # Demo pack orchestrator (prepare/verify/cleanup)
│   └── export_gnn_onnx.py       # Export PyG GNN model to ONNX
│
└── storage/                     # Runtime data (gitignored)
    ├── cases/{case_id}/
    │   ├── meta.json
    │   ├── trace.json
    │   ├── CAM_{case_id}.md
    │   └── CAM_{case_id}.pdf
    └── cache/research/          # SearXNG result cache (v3)
```

---

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| OS | Linux / WSL2 (Ubuntu 22.04+) |
| Python | 3.12 with `.venv` |
| Node.js | 18+ |
| Ollama | Running at `http://172.23.112.1:11434` |
| Models | `sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0` + `qwen2.5:3b` |
| SearXNG | Docker container at `localhost:8888` |

### One-command startup

```bash
# Clone and enter the repo
git clone https://github.com/Aqwerty321/Intelli-Credit.git
cd Intelli-Credit

# Create and activate Python venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install && cd ..

# Start everything (backend + frontend dev server + ORT WASM copy)
./scripts/start.sh
```

- **Backend** → [http://localhost:8000](http://localhost:8000)
- **Frontend** → [http://localhost:5173](http://localhost:5173)
- **API docs** → [http://localhost:8000/docs](http://localhost:8000/docs)

> `start.sh` automatically copies the ORT WASM runtime files from `node_modules/onnxruntime-web/dist/` to `frontend/public/models/` on every run (they are gitignored because they are large binaries).

### Backend only

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend only

```bash
cd frontend && npm run dev
```

### Health check

```bash
curl http://localhost:8000/health
# → {"status": "ok", "version": "3.0.0"}
```

---

## Backend API Reference

All endpoints are prefixed with `/api`.

### Cases

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cases/` | List all cases (summary array) |
| `POST` | `/api/cases/` | Create a new case (`CaseCreate` JSON body) |
| `GET` | `/api/cases/{id}` | Full case detail including officer notes |
| `DELETE` | `/api/cases/{id}` | Delete case and all associated files |
| `POST` | `/api/cases/{id}/documents` | Upload a document (PDF, MD, JSON, TXT) |
| `GET` | `/api/cases/{id}/cam` | Download CAM as Markdown (`.md`) |
| `GET` | `/api/cases/{id}/cam/pdf` | Download CAM as PDF (ReportLab) |
| `GET` | `/api/cases/{id}/graph` | Graph trace (nodes, edges, GNN results, cycles) |
| `POST` | `/api/cases/{id}/notes` | Add an officer note (body, tags, pinned) |
| `GET` | `/api/cases/{id}/notes` | List officer notes |
| `PATCH` | `/api/cases/{id}/notes/{nid}` | Partial update a note (body, tags, pinned) |
| `DELETE` | `/api/cases/{id}/notes/{nid}` | Delete a note |
| `GET` | `/api/cases/stats/dashboard` | Portfolio-level statistics |
| `GET` | `/api/cases/compare/bulk?ids=a,b,c` | Side-by-side comparison data (max 5 cases) |

### Run

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/run/{id}/stream` | SSE stream — runs the full appraisal pipeline and emits live events |
| `POST` | `/api/run/{id}/sync` | Synchronous appraisal (waits for completion, returns result) |

### SSE event types emitted by `/api/run/{id}/stream`

| Event | When |
|-------|------|
| `log` | Progress log line from any pipeline stage |
| `research_plan_ready` | ResearchRouter has planned the search queries |
| `evidence_scored` | EvidenceJudge has scored all findings |
| `claim_graph_ready` | ClaimGraph has extracted and cross-checked claims |
| `counterfactual_ready` | CounterfactualChallenger has built what-if scenarios |
| `complete` | Pipeline finished; payload contains full decision + trace |
| `error` | Unrecoverable pipeline error |

### Dashboard Stats response shape

```json
{
  "total_cases": 5,
  "completed_cases": 5,
  "decision_counts": { "APPROVE": 1, "CONDITIONAL": 1, "REJECT": 3 },
  "avg_risk": 0.71,
  "risk_distribution": [
    { "bucket": "0.0–0.2", "count": 0 },
    { "bucket": "0.2–0.4", "count": 1 },
    ...
  ],
  "sector_breakdown": { "Textiles": 1, "Pharma": 1, ... },
  "top_rules_fired": [ { "rule_id": "0005", "count": 3 }, ... ],
  "recent_activity": [ { "case_id": "...", "company_name": "...", "recommendation": "...", ... }, ... ]
}
```

---

## Frontend Pages & Components

### Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/` | `Dashboard` | Portfolio KPIs, verdict pie, risk histogram, rule heatmap, sector breakdown, activity timeline |
| `/cases` | `CaseList` | Sortable full case table with bulk stats bar and per-row delete |
| `/cases/new` | `CaseCreate` | New case submission form |
| `/cases/compare` | `CaseCompare` | Multi-case selector + side-by-side metric comparison |
| `/cases/:caseId` | `CaseDetail` | Tabbed case detail view |

### CaseDetail tabs

| Tab | Panels | Shown when |
|-----|--------|------------|
| **Overview** | KPIStrip, CaseHeader, RunPanel, PipelineTimeline | Always |
| **Trace** | TracePanel (rule firings, risk waterfall, graph summary) | After run |
| **Evidence** | EvidencePanel (findings list, corroboration stats) | After run |
| **Graph** | GraphPanel (D3 force graph, GNN results, cycle list, GraphPlayground) | After run |
| **Judge** | JudgePanel (evidence quality, claim graph, counterfactuals, search plan) | `schema_version === "v3"` |
| **CAM** | CAMPanel (markdown preview, PDF download, MD download) | After run |
| **Notes** | NotesPanel (CRUD, tags, pinned filter, search) | Always |
| **Documents** | DocumentsPanel (upload + list) | Always |

### Dashboard charts

| Chart | Type | Powered by |
|-------|------|-----------|
| Verdict distribution | Donut pie | Recharts `PieChart` |
| Risk score distribution | 5-bucket bar | Recharts `BarChart` |
| Top rules fired | Horizontal heatmap bars | CSS + React |
| Sector breakdown | Pie | Recharts `PieChart` |
| Recent activity | Vertical timeline | React + Tailwind |

### Visualisation components

| Component | What it renders |
|-----------|----------------|
| `RiskGauge` | Donut arc (220° sweep) with centred percentage label, colour-coded green/amber/red |
| `RiskWaterfall` | Stacked waterfall of per-rule risk adjustments from base score to final |
| `ClassRadar` | Spider/radar chart of GNN entity class scores |
| `CounterfactualBar` | Horizontal bar chart of Δ risk for each what-if scenario |
| `EvidenceScatter` | Confidence × relevance scatter plot of research findings |
| `ForceGraph` | D3 force-directed graph of borrower transaction network; node colour = role |
| `GraphPlayground` | Interactive ONNX GNN — edit node features in-browser and get live classification |

---

## Intelligence Pipeline

The pipeline is triggered via `GET /api/run/{id}/stream` (SSE) or `POST /api/run/{id}/sync` and executes these stages in order:

```
1. Ingest documents
   └── preprocess.py: normalise PDF/MD/JSON → plain text
   └── validator.py:  extract structured facts via regex matchers
   └── provenance.py: stamp source metadata

2. Lakehouse ETL
   └── db.py: load transactions into DuckDB, compute GST reconciliation,
              flag ITC excess, compute cash-flow velocity

3. Entity resolution
   └── resolver.py: fuzzy-match entity names across documents (RapidFuzz)

4. Graph construction
   └── builder.py:   build directed transaction graph (NetworkX)
   └── intelligence.py: run GNN classifier, detect cycles, score entities

5. Multi-agent research (parallel sub-pipeline)
   └── research_router.py:  LLM plans search queries (qwen2.5:3b)
   └── research_agent.py:   executes SearXNG searches, filters noise domains,
                             applies DOMAIN_TIERS confidence map, caches results
   └── evidence_judge.py:   scores and ranks findings (precision@10, corroboration%)
   └── claim_graph.py:      extracts claims, detects contradictions (qwen2.5:3b)
   └── counterfactual.py:   generates deterministic what-if scenarios

6. Rule engine
   └── rule_engine.py: evaluates all 10 YAML rules against extracted facts,
                       accumulates risk_adjustment, emits RuleFiring records

7. Final scoring
   └── Base risk + Σ rule adjustments + GNN risk contribution
   └── Hard-reject check (any rule with hard_reject=True → score = 1.0)
   └── Verdict threshold: <0.40 APPROVE, 0.40–0.69 CONDITIONAL, ≥0.70 REJECT

8. CAM generation
   └── generator.py:     Markdown CAM with full evidence citations
   └── pdf_generator.py: ReportLab PDF (title block, tables, risk gauge drawing,
                          rule waterfall, graph summary, fraud alerts, counterfactuals)

9. Trace serialisation
   └── Writes trace.json (schema v3) with all intelligence signals + v2_compat flag
```

### Trace schema v3 keys

```json
{
  "schema_version": "v3",
  "v2_compat": true,
  "orchestration_mode": "full|research_only|rules_only",
  "risk_score": 0.65,
  "recommendation": "CONDITIONAL",
  "rule_firings": [...],
  "graph_trace": { "node_count": 8, "edge_count": 11, "gnn_label": "ring", ... },
  "research_plan": { "queries": [...], "query_count": 6 },
  "evidence_judge": { "accepted": 7, "precision_at_10": 0.70, "corroborated": 4 },
  "claim_graph": { "claims": [...], "contradictions": [...] },
  "counterfactuals": [ { "scenario": "...", "delta_risk_score": -0.20 }, ... ],
  "orchestration_impact": { "pre_orchestration_risk_score": 0.50, ... },
  "fallbacks_used": []
}
```

---

## Rule Engine v2

Rules live in `rules/*.yml` and are loaded at startup. The engine evaluates all 10 rules against the facts extracted from the borrower's documents.

### Rule file schema (v2)

```yaml
version: "2.0"
rule_id: "0003"
rule_slug: "dpd_threshold"
description: "Elevated days-past-due flags repayment stress"
severity: "HIGH"
flag_type: "REPAYMENT_STRESS"
cam_section: "Credit History"

condition:
  type: threshold
  field: dpd_days          # Fact key extracted from documents
  direction: above          # above | below
  thresholds:
    - value: 90
      label: critical
      risk_adjustment: 0.40   # ← Must be on the threshold object (v2 requirement)
      hard_reject: true
    - value: 30
      label: moderate
      risk_adjustment: 0.20
```

> **Critical authoring rule:** `risk_adjustment` must be on each **threshold object**, not on the `action` block. Placing it on `action` silently produces `0.0` adjustment (v1 bug).

### The 10 rules

| ID | Rule | Severity | Hard Reject |
|----|------|----------|-------------|
| 0001 | GST ITC mismatch (GSTR-3B vs GSTR-2A excess) | HIGH | No |
| 0002 | Circular trading indicator | CRITICAL | Yes |
| 0003 | DPD threshold (>30 moderate, >90 critical) | HIGH | Yes (>90) |
| 0004 | Dishonoured cheques | MEDIUM | No |
| 0005 | CIBIL CMR threshold (>7 critical, >5 high) | HIGH | Yes (CMR >8) |
| 0006 | Revenue inflation vs bank statement | HIGH | No |
| 0007 | Promoter litigation / criminal cases | CRITICAL | Yes |
| 0008 | Capacity utilisation (<40% distress) | MEDIUM | No |
| 0009 | Sector headwind flag | LOW | No |
| 0010 | Collateral coverage ratio (<1.0× critical) | HIGH | Yes (<1.0×) |

---

## Graph & GNN Intelligence

### Transaction graph

Built by `services/graph/builder.py` from the case's transaction data:

- **Nodes**: Borrower, suppliers, buyers, banks, related parties, shells
- **Edges**: Directed transactions with amount and type attributes
- **Role detection**: `source_role` / `target_role` from document facts

### GNN model

A lightweight 2-layer Graph Convolutional Network trained to classify transaction graphs into 5 fraud topologies:

| Label | Description |
|-------|-------------|
| `clean` | Normal trade flows, no suspicious patterns |
| `ring` | Circular value transfer between a small set of entities |
| `star_seller` | Single entity acting as hub for many small shell buyers |
| `dense_cluster` | Over-connected sub-network suggesting round-tripping |
| `layered_chain` | Multi-hop value layering to obscure origin |

The GNN runs in three places:
1. **Server-side** (`services/graph/intelligence.py`) via PyTorch Geometric during pipeline execution
2. **Browser** (`frontend/src/services/gnn.js`) via ONNX Runtime Web WASM — no backend call needed
3. **GraphPlayground** — interactive in-browser inference where you can edit node feature vectors and see the classification change in real time

### Cycle detection

`intelligence.py` also runs `networkx.simple_cycles()` on the transaction graph to detect suspicious circular flows. Each detected cycle is reported in `graph_trace.suspicious_cycles` and surfaced in the Trace panel.

### Exporting the ONNX model

```bash
source .venv/bin/activate
python scripts/export_gnn_onnx.py
# Writes frontend/public/models/demo_graph_gnn.onnx + demo_graph_gnn_meta.json
```

---

## Research Agent System

The multi-agent research pipeline runs autonomously to gather public-domain intelligence on the borrower.

### Agents

#### `ResearchRouterAgent` (`research_router.py`)

Uses `qwen2.5:3b` to plan targeted search queries based on the borrower's company name, sector, and known risk signals. Falls back to a deterministic query template if the LLM is unavailable.

#### `ResearchAgent` (`research_agent.py`)

- Executes queries via SearXNG (`localhost:8888`)
- Applies a **26-domain blocklist** (Reddit, Cambridge Dictionary, Amazon, etc.) to filter noise
- Uses a **25-entry `DOMAIN_TIERS` confidence map** (RBI/SEBI = 0.95, ET/BL = 0.75, unknown = 0.40)
- Requires **full entity name phrase OR ≥2 significant words (>4 chars)** to match — prevents false positives
- Caches results at `storage/cache/research/<company>_v3_research.json` (delete to force re-research)
- **Stale marking**: regulatory/litigation findings from before 2021 get `stale=True` and `risk_impact` prefixed with `"stale_"` — they are kept for completeness but don't count toward the risk score

#### `EvidenceJudgeAgent` (`evidence_judge.py`)

Scores the collected findings using a composite metric:
- **Precision@10**: fraction of top-10 findings that are genuinely relevant
- **Corroboration**: findings confirmed by ≥2 independent sources
- **Source tier weighting**: high-tier sources get boosted acceptance scores

#### `ClaimGraph` (`claim_graph.py`)

Uses `qwen2.5:3b` to extract factual claims from evidence text and build a contradiction graph. Contradicting claims (e.g., two sources giving different revenue figures) are flagged and surfaced in the Judge panel.

#### `CounterfactualChallenger` (`counterfactual.py`)

Generates deterministic what-if scenarios:
- "What if DPD were cleared?" → removes DPD rule firings → reports Δ risk score
- "What if CMR improved to 4?" → removes CMR firing → reports Δ risk score
- Surfaced as a horizontal bar chart in the Judge panel and included in the PDF CAM

---

## CAM Generation (Markdown + PDF)

### Markdown (`services/cam/generator.py`)

Generates a structured Markdown CAM with sections: Executive Summary, Borrower Profile, Financial Analysis, Risk Factors, Evidence Summary, Graph Analysis, Recommendation.

Download via `GET /api/cases/{id}/cam`.

### PDF (`services/cam/pdf_generator.py`)

ReportLab-based multi-page PDF with professional styling:

| Section | Content |
|---------|---------|
| Title block | "CREDIT APPRAISAL MEMO", bank branding, date, classification |
| Borrower info | Company, loan amount, sector, purpose — formatted table |
| Verdict & risk | Colour-coded verdict badge + semi-circle gauge drawing (Wedge) |
| Executive summary | LLM-generated narrative |
| Rule firings | Waterfall table: rule, severity badge, risk adj, running total |
| Graph analysis | Nodes, edges, GNN label, cycles, suspicious entities |
| Fraud alerts | Red-highlighted hard-reject triggers |
| Evidence quality | Precision@10, corroboration %, top findings |
| Counterfactuals | What-if scenario table with Δ risk |
| Disclaimer | Legal boilerplate footer |

Download via `GET /api/cases/{id}/cam/pdf`.

---

## Demo Intelligence Pack

Five deterministic cases in `demo/intelligence_cases/` that exercise every intelligence layer:

| Case | Company | Verdict | Risk | Rules Fired | Key Signal |
|------|---------|---------|------|-------------|-----------|
| `approve` | Sunrise Textiles Pvt Ltd | **APPROVE** | 0.30 | 0 | CMR=3, DPD=0, clean ITC, capacity 78%, collateral 1.6× |
| `approve_plus` | Extended approve scenario | **APPROVE** | ~0.35 | 1 | Marginal sector headwind only |
| `conditional` | Apex Steel Components Ltd | **CONDITIONAL** | 0.65 | 3 | CMR=6 (+0.10), DPD=45 (+0.10), ITC 33% excess (+0.15) |
| `conditional_plus` | Extended conditional | **CONDITIONAL** | ~0.65 | 3 | Similar profile with litigation note |
| `reject` | Greenfield Pharma Industries | **REJECT** | 1.0 (hard) | 9 | CMR=9, DPD=120, circular trading, criminal cases, capacity 25% |

Each case folder contains:
- `seed.json` — `CaseCreate` API payload
- `facts.md` — parser-friendly document (regex-matched by `validator.py`)
- `transactions.json` — structured transaction data for graph construction
- `research_cache.json` — pre-shaped v3 research cache (avoids live SearXNG calls in tests)

### Running the demo pack

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

python scripts/demo_intelligence_pack.py prepare   # creates cases via API
python scripts/demo_intelligence_pack.py verify    # asserts verdicts + graph expectations
python scripts/demo_intelligence_pack.py cleanup   # deletes demo cases
```

---

## Test Suite

### Backend tests (pytest)

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short
# Expected: 221 PASS
```

| Module | Tests | Coverage |
|--------|-------|---------|
| `test_api.py` | 4 | Basic CRUD, health endpoint |
| `test_demo_cases.py` | 23 | Manifest-driven demo pack assertions |
| `test_graph_api.py` | 12 | Graph construction, GNN, cycle detection |
| `test_graph_trace.py` | 12 | Trace schema v3, graph_trace keys |
| `test_phase4_sse_order.py` | varies | SSE event ordering |
| `test_phase5_notes.py` | 19 | Notes CRUD, PATCH, DELETE, tags/pinned |
| `test_phase5_e2e_flow.py` | 3 | Full lifecycle, tag edges, 404 paths |
| `test_trace_v3.py` | varies | v3 schema keys present |
| `test_research_agent.py` | varies | Noise filtering, stale detection, entity matching |
| `test_rule_context_completeness.py` | varies | All 10 rules load and evaluate cleanly |
| `test_graph_intelligence.py` | varies | Unit tests for GNN + cycle detection |
| `test_counterfactual.py` | varies | Deterministic what-if output |

### Frontend tests (Vitest)

```bash
cd frontend && npm test
# Expected: 37 PASS (6 test files)
```

| File | Tests | Coverage |
|------|-------|---------|
| `Charts.test.jsx` | 6 | RiskGauge, RiskWaterfall rendering |
| `ConfirmModal.test.jsx` | 8 | Danger/safe modal interactions |
| `HealthBadge.test.jsx` | 4 | Healthy/Offline/checking states |
| `CaseListDelete.test.jsx` | 5 | Per-row delete confirm flow |
| `NotesList.test.jsx` | 7 | Notes CRUD UI, tag filtering |
| `GnnFeatures.test.js` | 7 | ONNX feature vector construction |

### E2E tests (Playwright — requires live servers)

```bash
# Terminal 1:
./scripts/start.sh

# Terminal 2:
cd frontend && npm run e2e
```

---

## Configuration & Environment

### Ollama endpoint

Set `OLLAMA_HOST` to override the default:

```bash
export OLLAMA_HOST=http://172.23.112.1:11434
```

Default: `http://172.23.112.1:11434` (WSL2 host IP).

### Models used

| Model | Used by | Size |
|-------|---------|------|
| `sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0` | Main reasoning, CAM generation | ~8 GB |
| `qwen2.5:3b` | ResearchRouter, EvidenceJudge, ClaimGraph | ~2 GB |

### SearXNG

Expects a running SearXNG instance at `http://localhost:8888`. Start with:

```bash
docker compose up -d searxng
```

### Presentation mode

Add `?presentation=1` to any URL (or set `VITE_PRESENTATION_MODE=1` at build time) to hide the sidebar and all debug/dev UI for clean screen-sharing.

### Research cache

To invalidate a cached research result:

```bash
rm storage/cache/research/<sanitized_company_name>_v3_research.json
```

Cache version is `"3"` — older cache files are automatically rejected and refreshed.

---

## Scripts Reference

| Script | Usage | Description |
|--------|-------|-------------|
| `scripts/start.sh` | `./scripts/start.sh` | Start backend + frontend dev server. Copies ORT WASM files. |
| `scripts/start.sh` | `./scripts/start.sh --no-frontend` | Backend only |
| `scripts/run_acceptance.sh` | `./scripts/run_acceptance.sh` | Full pytest suite |
| `scripts/judge_pack.sh` | `./scripts/judge_pack.sh` | Tests + showdown + scorecard → `reports/` |
| `scripts/judge_pack.sh` | `./scripts/judge_pack.sh --skip-tests` | Scorecard only (faster iteration) |
| `scripts/demo_intelligence_pack.py` | `python scripts/demo_intelligence_pack.py prepare` | Load demo cases via live API |
| `scripts/demo_intelligence_pack.py` | `python scripts/demo_intelligence_pack.py verify` | Assert demo case verdicts |
| `scripts/demo_intelligence_pack.py` | `python scripts/demo_intelligence_pack.py cleanup` | Remove demo cases |
| `scripts/export_gnn_onnx.py` | `python scripts/export_gnn_onnx.py` | Export GNN to ONNX for browser inference |

---

## Storage Layout

All runtime data lives under `storage/` (gitignored):

```
storage/
├── cases/
│   └── {case_id}/
│       ├── meta.json              # Case metadata (company, loan, status, created_at)
│       ├── trace.json             # Full decision trace (schema v3)
│       ├── CAM_{case_id}.md       # Markdown CAM
│       ├── CAM_{case_id}.pdf      # PDF CAM
│       └── docs/
│           └── {doc_id}.{ext}     # Uploaded documents
└── cache/
    └── research/
        └── {company}_v3_research.json   # SearXNG result cache
```

---

## License

Proprietary — Intelli-Credit is a private research prototype.
