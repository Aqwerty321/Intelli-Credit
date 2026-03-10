<p align="center">
  <h1 align="center">🏦 Intelli-Credit</h1>
  <p align="center">
    <strong>The AI Credit Analyst That Never Sleeps</strong>
  </p>
  <p align="center">
    <em>Turn 3 days of manual loan underwriting into 3 minutes of auditable AI reasoning.</em>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/react-18.3-61DAFB?logo=react&logoColor=white" alt="React 18" />
    <img src="https://img.shields.io/badge/fastapi-0.135-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/tests-231_pass-brightgreen" alt="Tests" />
    <img src="https://img.shields.io/badge/agents-5_autonomous-blueviolet" alt="Agents" />
    <img src="https://img.shields.io/badge/rules-10_neuro--symbolic-orange" alt="Rules" />
    <img src="https://img.shields.io/badge/100%25-local_&_private-critical" alt="Local" />
  </p>
</p>

---

> **Intelli-Credit** is a fully autonomous credit decisioning engine that ingests borrower documents,
> researches companies across the open web, builds transaction graphs, runs GNN fraud detection,
> fires deterministic risk rules, and generates bank-ready Credit Appraisal Memos — all on a single
> machine, with zero cloud dependencies, in minutes instead of days.

---

## The Problem

An MSME loan officer today spends **3–5 days per application**: manually reading PDFs, cross-checking GST returns against bank statements, Googling the borrower for red flags, running mental math on collateral coverage, and writing a Credit Appraisal Memo by hand. The process is slow, inconsistent, and impossible to audit after the fact.

## The Solution

Intelli-Credit replaces that entire workflow with a **9-stage AI pipeline** that streams results in real time:

```
📄 Documents In → 🔍 Facts Extracted → 🌐 Web Researched → 📊 Graph Analysed
     → ⚖️ Rules Fired → 🧮 Risk Scored → 📋 CAM Generated → ✅ Verdict Delivered
```

Every decision comes with a complete audit trail. Every risk basis point is explained. Every claim is sourced.

---

## At a Glance

| | |
|:---|:---|
| **13,400+** lines of Python | **4,100+** lines of React/JS |
| **9-stage** intelligence pipeline | **5 autonomous** research agents |
| **10 neuro-symbolic** risk rules | **5-signal** composite risk scoring |
| **231 backend** + **37 frontend** tests | **5 GNN fraud** topologies |
| **15+ regex** fact extractors | **25-tier** source confidence map |
| **26-domain** noise blocklist | **3 demo cases** auto-seeded on startup |
| **2 LLM models** (DeepSeek-R1 8B + Qwen 2.5 3B) | **0 cloud APIs** |

---

## Key Capabilities

### 🔬 Multi-Agent Research Intelligence
Five specialised agents collaborate autonomously — no human in the loop:

| Agent | What It Does |
|-------|-------------|
| **ResearchRouter** | Uses LLM to plan 8–12 targeted search queries from borrower context, financial data, and sector signals |
| **ResearchAgent** | Executes searches via SearXNG, filters 26 noise domains (Reddit, Wikipedia, Amazon…), scores sources on a 25-tier confidence map (RBI/SEBI = 0.95, unknown blog = 0.40) |
| **EvidenceJudge** | Scores every finding by precision@10 and cross-source corroboration — a claim backed by 3 independent sources scores higher than one backed by 1 |
| **ClaimGraph** | Extracts concrete factual claims from evidence, then detects contradictions between sources |
| **Counterfactual** | Generates what-if scenarios: *"What if DPD were 0 instead of 120?"* — shows the risk delta, making the model's reasoning transparent and challengeable |

### 🧠 Neuro-Symbolic Risk Engine
10 domain-expert rules authored in a strict YAML v2 schema — no black boxes:

| Rule | What It Catches | Hard Reject? |
|------|----------------|:---:|
| GST ITC Mismatch | GSTR-3B claims more ITC than GSTR-2A shows | — |
| Circular Trading | Cycle detected in transaction graph | ✓ |
| DPD Threshold | Days past due > 30 / > 90 | ✓ (>90) |
| Dishonoured Cheques | Bounced cheques in CIBIL report | — |
| CIBIL CMR | CMR score > 5 / > 7 / > 8 | ✓ (>8) |
| Revenue Inflation | Declared revenue vs bank cash-flow mismatch | — |
| Promoter Litigation | Criminal cases, wilful defaulter, DIN disqualified | ✓ |
| Capacity Utilisation | Operating below 40% capacity | — |
| Sector Headwind | Industry in regulatory or cyclical distress | — |
| Collateral Coverage | Coverage ratio below 1.0x | ✓ (<1.0x) |

Every rule fires independently, emits a severity-tagged RuleFiring record, and contributes a precise risk adjustment. **No rule is a black box** — the trace shows exactly which threshold was crossed and by how much.

### 📊 GNN Fraud Detection — In Your Browser
A 2-layer Graph Convolutional Network (PyTorch Geometric) classifies borrower transaction networks into 5 fraud topologies:

| Topology | What It Means |
|----------|--------------|
| **clean** | Normal trade flows — no anomalies |
| **ring** | Circular value transfer between a small group |
| **star_seller** | Single hub entity with many shell counterparties |
| **dense_cluster** | Over-connected sub-network suggesting round-tripping |
| **layered_chain** | Multi-hop layering to obscure value origin |

The GNN runs server-side via PyTorch Geometric **and** client-side via ONNX Runtime Web — users can interactively edit node features in the **GraphPlayground** and watch the classification update live, with zero backend calls.

### 🎯 Multi-Signal Risk Scoring
The final risk score is not a single model's opinion — it is a **weighted composition of 5 independent signals**:

```
risk_score = clamp(0, 1,
    base_prior           (0.15)        — every application starts here
  + llm_classification   (0.00-0.40)   — from LOW / MEDIUM / HIGH / CRITICAL
  + gnn_graph_risk       (0.00-0.15)   — ring=0.15, star=0.08, dense=0.12, chain=0.05
  + negative_evidence    (0.00-0.05)   — bonus if 3+ negative research findings
  + rule_adjustments     (variable)    — deterministic per-rule deltas
)
```

Hard-reject override: any rule flagged `hard_reject: true` forces the score to **1.0** regardless of other signals.

**Verdict thresholds:** `< 0.40` APPROVE | `0.40-0.69` CONDITIONAL | `>= 0.70` REJECT

### 📄 Bank-Ready CAM Output
Generates professional Credit Appraisal Memos in two formats:

- **Markdown** — Executive Summary, Borrower Profile, Financial Analysis, Risk Factors, Evidence Summary, Graph Analysis, Counterfactuals, Recommendation
- **PDF** (ReportLab) — multi-page layout with colour-coded verdict badge, semi-circle risk gauge, rule-firing waterfall table, graph analysis, evidence quality metrics, counterfactual appendix, and legal disclaimer

### ⚡ Real-Time Streaming
The full pipeline streams to the frontend via Server-Sent Events. Watch each agent report in as it works:

`search_plan_ready` → `evidence_scored` → `claim_graph_ready` → `counterfactual_ready` → `complete`

No waiting for a spinner to finish — see every stage as it happens.

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                      React 18 + Vite Frontend                         │
│  Dashboard · CaseList · CaseDetail · CaseCompare · CaseCreate        │
│  7 chart components · 11 panel components · ONNX GNN Playground       │
└──────────────────────────────┬────────────────────────────────────────┘
                               │ REST + SSE
┌──────────────────────────────▼────────────────────────────────────────┐
│                      FastAPI Backend (port 8000)                      │
│  /api/cases · /api/run · /api/health · Swagger docs at /docs          │
└──┬──────────────┬──────────────┬───────────────┬─────────────────────┘
   │              │              │               │
   ▼              ▼              ▼               ▼
 Ingestor      Lakehouse     Rule Engine    Agent Orchestrator
 (PDF/MD/JSON  (DuckDB,      (10 YAML v2   ├─ ResearchRouter  → LLM query planner
  + 15 regex    zero-copy     rules with    ├─ ResearchAgent   → SearXNG + caching
  extractors)   Arrow)        audit trail)  ├─ EvidenceJudge   → precision@10 scorer
                                            ├─ ClaimGraph      → contradiction detector
   ▼              ▼                         └─ Counterfactual  → what-if challenger
 Entity        Graph Builder
 Resolution    (NetworkX)         CAM Generator
 (RapidFuzz)      │               (Markdown + ReportLab PDF)
                  ▼
              GNN Intelligence
              (PyTorch Geometric + ONNX Runtime Web)
```

---

## Tech Stack

### Backend

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.135, Uvicorn, SSE via sse-starlette |
| LLM (reasoning) | Ollama — DeepSeek-R1 8B Q8 distill (abliterated) |
| LLM (agents) | Ollama — Qwen 2.5 3B (Router, Judge, ClaimGraph) |
| Web search | SearXNG (self-hosted Docker container) |
| Analytics | DuckDB 1.4 (zero-copy Arrow, in-process) |
| Graph | NetworkX 3.6, PyTorch Geometric |
| Browser ML | ONNX Runtime Web 1.24 (WASM + SIMD) |
| PDF | ReportLab 4.4 |
| Entity matching | RapidFuzz 3.14 |

### Frontend

| Layer | Technology |
|-------|-----------|
| Framework | React 18.3, Vite 5.4 |
| Routing | React Router DOM 6.28 |
| Styling | Tailwind CSS 3.4 |
| Charts | Recharts 3.8 (pie, bar, radar, scatter, waterfall) |
| Graph viz | D3.js 7.9 (force-directed layout) |
| In-browser ML | ONNX Runtime Web (GNN inference, no server needed) |
| Testing | Vitest + happy-dom, Playwright E2E |

---

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| **OS** | Linux or WSL2 (Ubuntu 22.04+) |
| **Python** | 3.12 |
| **Node.js** | 18+ |
| **Ollama** | Running with `deepseek-r1-8b` + `qwen2.5:3b` models loaded |
| **SearXNG** | Docker container on `localhost:8888` (for live web research) |

### Install and Launch

```bash
git clone https://github.com/Aqwerty321/Intelli-Credit.git
cd Intelli-Credit

# Python
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Launch everything (backend :8000 + frontend :5173)
./scripts/start.sh
```

### Verify

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "3.0.0"}
```

Open `http://localhost:5173` — three demo cases are **auto-seeded on first startup** with full analytics. Start exploring immediately, no setup required.

---

## Demo Cases — Try It Now

Three pre-built intelligence cases ship with the system, each exercising different risk profiles and decision paths:

| Company | Verdict | Risk | Rules Fired | What Makes It Interesting |
|---------|:-------:|:----:|:-----------:|--------------------------|
| **Sunrise Textiles Pvt Ltd** | ✅ APPROVE | 0.25 | 0 | Clean case — CMR 3, zero DPD, GST matches, 78% capacity, 1.6x collateral. Demonstrates the system's ability to confidently approve. |
| **Apex Steel Components Ltd** | ⚠️ CONDITIONAL | 0.65 | 3 | Borderline — CMR 6 triggers +0.10, DPD 45 triggers +0.10, ITC 33% excess triggers +0.15. Shows nuanced multi-rule interaction. |
| **Greenfield Pharma Industries** | ❌ REJECT | 1.00 | 9 | Maximum risk — CMR 9, DPD 120, circular trading in graph, criminal cases on promoter, 25% capacity. Hard-reject cascade. |

Each case comes with parser-friendly documents, structured transactions, and pre-shaped research caches. **No live Ollama or SearXNG needed** to explore the full UI.

---

## The 9-Stage Pipeline

When you hit **Run Appraisal**, nine stages execute in sequence, streaming real-time progress to the UI:

### Stage 1 — Document Ingestion
Parse uploaded PDFs (PyMuPDF), Markdown, and structured JSON. Extract **15+ structured financial facts** via regex: GST figures, CIBIL CMR, DPD days, collateral ratios, capacity utilisation, promoter details, revenue figures, and more.

### Stage 2 — Lakehouse ETL
Load transactions into DuckDB. Compute GST reconciliation (GSTR-2A vs GSTR-3B), flag ITC excess, calculate cash-flow velocity.

### Stage 3 — Entity Resolution
RapidFuzz matches entity names across documents — suppliers, buyers, related parties — building a unified entity graph even when names are inconsistently spelled across filings.

### Stage 4 — Transaction Graph + GNN
Build a directed transaction graph (NetworkX). Run the GCN to classify the network topology. Detect cycles via `networkx.simple_cycles` for explicit circular flow identification.

### Stage 5 — Multi-Agent Research
Five agents collaborate: plan queries, search the web, score evidence, extract claims, detect contradictions, challenge conclusions. All cached per-company with version-tracked invalidation.

### Stage 6 — Rule Engine
10 YAML v2 rules fire independently against extracted facts. Each produces a RuleFiring with severity, risk delta, and CAM section reference.

### Stage 7 — Multi-Signal Risk Scoring
Compose the final risk score from 5 independent sources. Apply hard-reject overrides. Map to verdict.

### Stage 8 — CAM Generation
Render the Credit Appraisal Memo in Markdown and PDF with full evidence citations, risk gauge, waterfall charts, and counterfactual appendix.

### Stage 9 — Trace Serialisation
Write a complete `trace.json` (schema v3) capturing every signal, every rule, every agent output — a full audit trail for regulatory compliance.

---

## Frontend

### Dashboard
Portfolio-level KPIs: case count by verdict, risk score distribution histogram, rule heatmap showing which rules fire most frequently, sector breakdown, and activity timeline.

### Case Detail — 8 Interactive Tabs

| Tab | What You See |
|-----|-------------|
| **Overview** | KPI strip (verdict, risk, rules fired, evidence count, graph label), run button with live SSE progress log, pipeline stage timeline |
| **Trace** | Every rule that fired with risk adjustments, risk waterfall chart, full LLM risk assessment with thinking chain, graph classification summary |
| **Evidence** | Research findings with source-tier badges (Government / Premium / News), relevance scores, and corroboration indicators |
| **Graph** | Interactive D3 force-directed transaction graph with colour-coded entities, GNN classification, cycle list, and the **ONNX GraphPlayground** for live in-browser inference |
| **Judge** | Evidence quality metrics (precision@10, corroboration %), claim graph with contradiction highlighting, counterfactual what-if bar chart, search plan |
| **CAM** | Rendered Markdown with download buttons for `.md` and `.pdf` |
| **Notes** | Officer notes with CRUD, tagging, pinning, and filter-by-tag |
| **Documents** | Upload and manage borrower documents |

### 7 Visualisation Components

| Component | Description |
|-----------|-------------|
| **RiskGauge** | 220 degree donut arc with centred percentage — green to amber to red |
| **RiskWaterfall** | Stacked waterfall showing per-rule contribution from base to final score |
| **ClassRadar** | Spider chart of GNN class probabilities |
| **CounterfactualBar** | Horizontal bars showing delta risk for each what-if scenario |
| **EvidenceScatter** | Confidence x relevance scatter plot |
| **ForceGraph** | D3 force-directed transaction network — drag, zoom, hover |
| **GraphPlayground** | Edit node features, get instant ONNX GNN inference in-browser |

### Case Comparison
Select 2–5 cases for side-by-side metric comparison across risk scores, rule fires, evidence counts, and graph classifications.

---

## API Reference

Base URL: `http://localhost:8000` — interactive Swagger docs at `/docs`

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cases/` | List all cases |
| `POST` | `/api/cases/` | Create a new case |
| `GET` | `/api/cases/{id}` | Full case detail (includes officer notes) |
| `DELETE` | `/api/cases/{id}` | Delete case and all associated files |
| `POST` | `/api/cases/{id}/documents` | Upload document (PDF, MD, JSON, TXT) |
| `GET` | `/api/cases/{id}/cam` | Download CAM (Markdown) |
| `GET` | `/api/cases/{id}/cam/pdf` | Download CAM (PDF) |
| `GET` | `/api/cases/{id}/graph` | Graph data (nodes, edges, GNN result, cycles) |
| `POST` | `/api/cases/{id}/notes` | Add officer note |
| `GET` | `/api/cases/{id}/notes` | List officer notes |
| `PATCH` | `/api/cases/{id}/notes/{nid}` | Partial update note (body, tags, pinned) |
| `DELETE` | `/api/cases/{id}/notes/{nid}` | Delete note |
| `GET` | `/api/cases/stats/dashboard` | Portfolio-wide statistics |
| `GET` | `/api/cases/compare/bulk?ids=a,b,c` | Compare up to 5 cases side-by-side |

### Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/run/{id}/stream` | SSE stream — runs full pipeline, emits live events |
| `POST` | `/api/run/{id}/sync` | Synchronous run — returns completed result |

### SSE Event Types

| Event | When |
|-------|------|
| `log` | Each pipeline stage progress update |
| `research_plan_ready` | Search queries planned by ResearchRouter |
| `evidence_scored` | Findings scored by EvidenceJudge |
| `claim_graph_ready` | Claims and contradictions extracted |
| `counterfactual_ready` | What-if scenarios generated |
| `complete` | Final decision trace |
| `error` | Pipeline failure |

---

## Test Suite

```bash
# Backend — 231 tests
source .venv/bin/activate && python -m pytest tests/ -v --tb=short

# Frontend — 37 tests
cd frontend && npm test

# E2E (requires live servers via ./scripts/start.sh)
cd frontend && npm run e2e
```

Backend coverage: API CRUD, demo manifest assertions, graph + GNN + cycle detection, trace schema v3 validation, SSE event ordering, officer notes lifecycle, research agent filtering, rule engine completeness, counterfactual generation, full case lifecycle.

---

## Project Structure

```
Intelli-Credit/
├── app/                            # FastAPI application
│   ├── main.py                     # App init, CORS, auto-seeder, lifespan
│   └── api/
│       ├── cases.py                # Case CRUD, stats, compare, CAM download, notes
│       ├── run.py                  # SSE pipeline streaming endpoint
│       └── autofetch.py            # Auto-fetch enrichment
│
├── services/                       # Core intelligence (34 Python modules)
│   ├── pipeline.py                 # 9-stage orchestrator (880 lines)
│   ├── agents/                     # 5-agent research system (2,200+ lines)
│   │   ├── orchestrator.py         # Agent coordinator
│   │   ├── research_agent.py       # SearXNG researcher + caching
│   │   ├── research_router.py      # LLM search query planner
│   │   ├── evidence_judge.py       # Precision@10 evidence scorer
│   │   ├── claim_graph.py          # Claim extraction + contradiction detection
│   │   └── counterfactual.py       # What-if scenario generator
│   ├── cam/                        # CAM generation
│   │   ├── generator.py            # Markdown CAM
│   │   └── pdf_generator.py        # ReportLab PDF with risk gauge
│   ├── graph/                      # Graph intelligence
│   │   ├── builder.py              # Transaction graph (NetworkX)
│   │   └── intelligence.py         # GNN classification + cycle detection
│   ├── reasoning/
│   │   └── rule_engine.py          # YAML v2 rule engine
│   ├── ingestor/                   # Document processing
│   │   ├── preprocess.py           # Document normalisation
│   │   ├── validator.py            # 15+ regex fact extractors
│   │   └── provenance.py           # Source tracking
│   ├── lakehouse/
│   │   └── db.py                   # DuckDB ETL
│   ├── entity_resolution/
│   │   └── resolver.py             # RapidFuzz entity matching
│   └── cognitive/
│       └── engine.py               # DeepSeek-R1 reasoning wrapper
│
├── rules/                          # 10 YAML v2 rule definitions
├── frontend/                       # React + Vite (37 modules, 4,100+ lines)
│   └── src/
│       ├── App.jsx                 # 5 routes
│       ├── components/
│       │   ├── charts/             # 7 viz: Gauge, Waterfall, Radar, Scatter, Force, Playground
│       │   └── panels/             # 11 panels: KPI, Trace, Evidence, Graph, Judge, CAM, Notes
│       └── services/
│           ├── api.js              # Centralised async API client
│           └── gnn.js              # ONNX Runtime Web GNN inference
│
├── demo/                           # 3 intelligence cases + seed data
├── tests/                          # 231 backend tests (20 test files)
├── templates/                      # CAM document templates
├── scripts/                        # start.sh, run_acceptance.sh, judge_pack.sh
└── storage/                        # Runtime data (gitignored)
    ├── cases/{case_id}/            # Per-case: meta, docs, traces, CAMs
    ├── cache/research/             # SearXNG result cache (v3)
    └── lakehouse.duckdb            # Analytics database
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://172.23.112.1:11434` | Ollama API endpoint |
| `SEARXNG_URL` | `http://localhost:8888` | SearXNG search endpoint |
| `VITE_PRESENTATION_MODE` | `0` | Set `1` to hide sidebar and debug UI for demos |

### Models

| Model | Purpose | VRAM |
|-------|---------|------|
| `deepseek-r1-8b-llama-distill-abliterated-q8_0` | Primary reasoning, risk assessment, CAM narrative | ~8 GB |
| `qwen2.5:3b` | Agent coordination (Router, Judge, ClaimGraph) | ~2 GB |

---

## Scripts

| Script | Description |
|--------|-------------|
| `./scripts/start.sh` | One-command startup (backend + frontend + WASM copy) |
| `./scripts/start.sh --no-frontend` | Backend only |
| `./scripts/run_acceptance.sh` | Run full backend test suite |
| `./scripts/judge_pack.sh` | Tests + showdown + scorecard into reports/ |
| `python scripts/export_gnn_onnx.py` | Export GNN to ONNX for browser inference |
| `python scripts/demo_intelligence_pack.py` | Demo case lifecycle: prepare / verify / cleanup |

---

## Why Fully Local?

Credit appraisal involves **highly sensitive financial data** — borrower tax returns, bank statements, CIBIL reports, promoter criminal records. Intelli-Credit is designed so that:

| Principle | How |
|-----------|-----|
| **Zero data exfiltration** | No API calls to OpenAI, Anthropic, Google, or any cloud service — ever |
| **No billing surprises** | All inference runs on your own GPU via Ollama |
| **Regulatory compliance** | Data residency is trivially satisfied when data never leaves the machine |
| **Reproducible** | Deterministic rule engine + cached research = identical results on re-run |
| **Air-gappable** | With models and caches pre-loaded, the system runs fully offline |

---

## License

Proprietary — Intelli-Credit is a private research prototype.
