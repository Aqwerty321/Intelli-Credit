<p align="center">
  <h1 align="center">Intelli-Credit</h1>
  <p align="center">
    <strong>AI-Powered Credit Decisioning Engine for MSME Lending</strong>
  </p>
  <p align="center">
    Fully local &nbsp;·&nbsp; Zero cloud dependencies &nbsp;·&nbsp; Complete audit trail
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12" />
    <img src="https://img.shields.io/badge/react-18.3-61DAFB?logo=react&logoColor=white" alt="React 18" />
    <img src="https://img.shields.io/badge/fastapi-0.135-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/tests-231%20backend%20%7C%2037%20frontend-brightgreen" alt="Tests" />
    <img src="https://img.shields.io/badge/license-proprietary-red" alt="License" />
  </p>
</p>

---

Intelli-Credit transforms the traditional MSME credit appraisal workflow — a process that typically takes a loan officer **3–5 days** of manual document review, web research, and memo writing — into an **automated, auditable, AI-driven pipeline** that delivers a fully reasoned Credit Appraisal Memo in minutes.

Every component runs **locally on a single GPU workstation**. No data leaves the machine. No cloud APIs. No billing. No vendor lock-in.

---

## Highlights

**🔍 Multi-Agent Research Intelligence** — A 5-agent orchestration system autonomously researches borrowers across the public web, plans targeted search queries via LLM, scores evidence quality, extracts and cross-references factual claims, detects contradictions, and challenges its own conclusions with counterfactual scenarios.

**🧠 Neuro-Symbolic Risk Engine** — 10 domain-expert YAML rules (GST reconciliation, CIBIL CMR thresholds, circular trading indicators, promoter litigation flags) fire deterministic risk adjustments with full audit traces. Every basis point added to the risk score is explained.

**📊 GNN Fraud Detection — In Your Browser** — A Graph Neural Network classifies borrower transaction networks into 5 fraud topologies (ring trading, star-seller schemes, dense clusters, layered chains). The GNN runs server-side via PyTorch Geometric *and* client-side via ONNX Runtime Web — users can interactively edit node features and watch the classification update in real time.

**📄 Professional CAM Output** — Generates bank-ready Credit Appraisal Memos in both Markdown and styled PDF (ReportLab), complete with risk gauge visuals, rule-firing waterfall tables, graph analysis, evidence citations, and counterfactual appendices.

**⚡ Real-Time Streaming** — The full pipeline streams progress to the frontend via Server-Sent Events. Watch each agent report in as it finishes — search plan, evidence scores, claim graph, counterfactuals — all before the final verdict lands.

**🎯 Multi-Signal Risk Scoring** — Risk scores aren't arbitrary. They're composed from 5 independent signal sources: base prior + LLM risk classification + GNN graph label + negative evidence density + deterministic rule adjustments — all clamped, weighted, and auditable.

---

## What It Does

Intelli-Credit automates the end-to-end **Credit Appraisal Memo (CAM)** workflow:

| Step | What happens | How |
|------|-------------|-----|
| **1. Ingest** | Drag-and-drop borrower documents (PDF, Markdown, JSON) | PyMuPDF OCR + regex fact extraction |
| **2. Extract** | Pull structured facts: GST figures, CIBIL CMR, DPD history, collateral ratios, capacity utilisation | 15+ regex matchers in `validator.py` |
| **3. Research** | Autonomously search the public web for borrower intelligence | 5-agent LLM pipeline + SearXNG |
| **4. Graph** | Build a transaction graph, run GNN classification, detect suspicious cycles | NetworkX + PyTorch Geometric |
| **5. Rules** | Fire 10 neuro-symbolic rules against extracted facts | YAML DSL v2 rule engine |
| **6. Score** | Synthesise all signals into a multi-source risk score | 5-signal weighted composition |
| **7. Decide** | Output a verdict: `APPROVE` / `CONDITIONAL` / `REJECT` | Threshold-based with hard-reject overrides |
| **8. Generate** | Produce a bank-ready CAM with full evidence citations | Markdown + ReportLab PDF |
| **9. Present** | Display everything in an interactive dashboard | React + D3 + Recharts + ONNX |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                            │
│   Dashboard · CaseList · CaseDetail · CaseCompare                  │
│   D3 ForceGraph · Recharts · ONNX GNN Playground                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────▼──────────────────────────────────────────┐
│                    FastAPI Backend                                   │
│   /api/cases · /api/run · /api/health                               │
└──┬──────────────┬─────────────┬───────────────┬─────────────────────┘
   │              │             │               │
   ▼              ▼             ▼               ▼
 Ingestor     Lakehouse     Rule Engine    Agent Orchestrator
 (PDF/MD/     (DuckDB)      (10 YAML v2   ├── ResearchRouter (LLM query planner)
  JSON OCR)                  rules)        ├── ResearchAgent  (SearXNG + 26-domain blocklist)
                                           ├── EvidenceJudge  (precision@10 scorer)
   ▼                                       ├── ClaimGraph     (contradiction detector)
 Graph Builder                             └── Counterfactual (what-if challenger)
 (NetworkX)
   │
   ▼
 GNN Intelligence              CAM Generator
 (PyTorch Geometric +          (Markdown + ReportLab PDF)
  ONNX Runtime Web)
```

---

## Tech Stack

### Backend

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.135 · Uvicorn · SSE via `sse-starlette` |
| LLM (primary) | Ollama — DeepSeek-R1 8B (Q8 distill, abliterated) |
| LLM (agents) | Ollama — Qwen 2.5 3B (Router, Judge, ClaimGraph) |
| Web search | SearXNG (self-hosted, Docker) |
| Analytics | DuckDB 1.4 (zero-copy Arrow, in-process) |
| Graph | NetworkX 3.6 · PyTorch Geometric |
| Browser ML | ONNX Runtime Web 1.24 (WASM + SIMD) |
| PDF | ReportLab 4.4 |
| Entity matching | RapidFuzz 3.14 |

### Frontend

| Layer | Technology |
|-------|-----------|
| Framework | React 18.3 · Vite 5.4 |
| Routing | React Router DOM 6.28 |
| Styling | Tailwind CSS 3.4 |
| Charts | Recharts 3.8 (pie, bar, radar, scatter, waterfall) |
| Graph | D3.js 7.9 (force-directed layout) |
| In-browser ML | ONNX Runtime Web (GNN inference, no backend needed) |
| Testing | Vitest + happy-dom · Playwright E2E |

---

## Quick Start

### Prerequisites

| Requirement | Details |
|-------------|---------|
| OS | Linux or WSL2 (Ubuntu 22.04+) |
| Python | 3.12 |
| Node.js | 18+ |
| Ollama | Running with `deepseek-r1-8b` + `qwen2.5:3b` models pulled |
| SearXNG | Docker container on `localhost:8888` |

### Install & launch

```bash
git clone https://github.com/Aqwerty321/Intelli-Credit.git
cd Intelli-Credit

# Python environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Launch (backend on :8000, frontend on :5173)
./scripts/start.sh
```

### Verify

```bash
curl http://localhost:8000/health
# {"status": "ok", "version": "3.0.0"}
```

Three pre-built demo cases (APPROVE, CONDITIONAL, REJECT) are automatically seeded on first startup with full analytics — open [http://localhost:5173](http://localhost:5173) and start exploring immediately.

---

## The Intelligence Pipeline

When you hit **Run Appraisal** on a case, the system executes a 9-stage pipeline — streaming progress to the UI in real time via SSE:

### Stage 1 — Document Ingestion
Normalise uploaded PDFs, Markdown files, and structured JSON into plain text. Extract **15+ structured financial facts** via regex matchers: GST figures, CIBIL CMR, DPD days, collateral coverage, capacity utilisation, promoter details, revenue, and more.

### Stage 2 — Lakehouse ETL
Load transactions into **DuckDB** (in-process, zero-copy Arrow). Compute GST reconciliation (GSTR-2A vs GSTR-3B), flag ITC excess, calculate cash-flow velocity metrics.

### Stage 3 — Entity Resolution
**RapidFuzz** fuzzy-matches entity names across documents — suppliers, buyers, related parties — to build a unified entity graph even when names are inconsistently spelled.

### Stage 4 — Transaction Graph + GNN
Build a directed transaction graph (NetworkX). Run a **2-layer Graph Convolutional Network** (PyTorch Geometric) to classify the network into one of 5 fraud topologies:

| Topology | Signal |
|----------|--------|
| `clean` | Normal trade flows |
| `ring` | Circular value transfer between a small group |
| `star_seller` | Single hub entity with many shell counterparties |
| `dense_cluster` | Over-connected sub-network suggesting round-tripping |
| `layered_chain` | Multi-hop layering to obscure value origin |

Cycle detection (`networkx.simple_cycles`) supplements the GNN with explicit circular flow identification.

### Stage 5 — Multi-Agent Research
Five specialised agents collaborate autonomously:

| Agent | Role | Model |
|-------|------|-------|
| **ResearchRouter** | Plans 8–12 targeted search queries using borrower context, financial data, and sector signals | Qwen 2.5 3B |
| **ResearchAgent** | Executes SearXNG searches, filters 26 noise domains, applies 25-tier source confidence map (RBI=0.95, unknown=0.40), caches results | — |
| **EvidenceJudge** | Scores findings by precision@10 and cross-source corroboration | Qwen 2.5 3B |
| **ClaimGraph** | Extracts factual claims from evidence, detects contradictions between sources | Qwen 2.5 3B |
| **Counterfactual** | Generates deterministic what-if scenarios ("What if DPD were 0?") and reports Δ risk | Deterministic |

Research results are cached per-company (`storage/cache/research/`) with automatic cache-version invalidation.

### Stage 6 — Rule Engine
10 YAML rules (schema v2) evaluate against extracted facts. Each rule fires independently, emitting a `RuleFiring` record with severity, risk adjustment amount, and CAM section reference. Hard-reject rules (circular trading, extreme DPD, critical CMR, severe collateral shortfall) force `risk_score = 1.0` regardless of other signals.

### Stage 7 — Multi-Signal Risk Scoring

The final risk score is composed from **5 independent sources**:

```
risk_score = clamp(0, 1,
    base_prior (0.15)
  + llm_classification (0.00–0.40, from LOW/MEDIUM/HIGH/CRITICAL)
  + gnn_label_risk     (0.00–0.15, non-synthesized graphs only)
  + negative_evidence   (0.00–0.05, if ≥3 negative findings)
  + Σ rule_adjustments  (from rule engine)
)
```

Hard-reject override: if any rule has `hard_reject: true`, the score is forced to `1.0`.

Verdict thresholds: `< 0.40` → APPROVE · `0.40–0.69` → CONDITIONAL · `≥ 0.70` → REJECT

### Stage 8 — CAM Generation
Render a bank-ready **Credit Appraisal Memo** in two formats:

- **Markdown** — structured sections: Executive Summary, Borrower Profile, Financial Analysis, Risk Factors, Evidence Summary, Graph Analysis, Counterfactuals, Recommendation
- **PDF** (ReportLab) — professional multi-page layout with colour-coded verdict badge, semi-circle risk gauge, rule-firing waterfall table, graph analysis section, evidence quality metrics, counterfactual appendix, and legal disclaimer

### Stage 9 — Trace Serialisation
Write a complete **trace.json** (schema v3) capturing every signal, every rule firing, every agent output, and every intermediate score — providing a full audit trail for regulatory compliance.

---

## The 10 Rules

| # | Rule | What it catches | Severity | Hard Reject? |
|---|------|----------------|----------|:------------:|
| 0001 | GST ITC Mismatch | GSTR-3B claims more ITC than GSTR-2A shows | HIGH | — |
| 0002 | Circular Trading | Cycle detected in transaction graph | CRITICAL | ✓ |
| 0003 | DPD Threshold | Days past due > 30 (moderate) or > 90 (critical) | HIGH | ✓ (>90) |
| 0004 | Dishonoured Cheques | Bounced cheques in CIBIL report | MEDIUM | — |
| 0005 | CIBIL CMR | CMR score > 5 (high) or > 7 (critical) | HIGH | ✓ (>8) |
| 0006 | Revenue Inflation | Declared revenue vs bank statement mismatch | HIGH | — |
| 0007 | Promoter Litigation | Criminal cases, wilful defaulter, DIN disqualification | CRITICAL | ✓ |
| 0008 | Capacity Utilisation | Operating below 40% capacity | MEDIUM | — |
| 0009 | Sector Headwind | Industry in regulatory or cyclical distress | LOW | — |
| 0010 | Collateral Coverage | Coverage ratio below 1.0× | HIGH | ✓ (<1.0×) |

Rules are authored in a strict YAML v2 schema with `risk_adjustment` on each threshold object and mandatory `direction: above|below` on conditions.

---

## Frontend

### Pages

| Route | View | Description |
|-------|------|-------------|
| `/` | **Dashboard** | Portfolio KPIs, verdict distribution pie, risk histogram, rule heatmap, sector breakdown, activity timeline |
| `/cases` | **Case List** | Sortable table with status badges, per-row delete, bulk statistics bar |
| `/cases/new` | **New Case** | Borrower submission form with sector/location autocomplete |
| `/cases/compare` | **Compare** | Side-by-side metric comparison for 2–5 selected cases |
| `/cases/:id` | **Case Detail** | Tabbed deep-dive into a single case |

### Case Detail Tabs

| Tab | What you see |
|-----|-------------|
| **Overview** | KPI strip (verdict · risk score · rules fired · evidence count · graph label), run button with live SSE log, pipeline timeline |
| **Trace** | Every rule that fired with risk adjustment amounts, risk waterfall chart, LLM risk assessment with full thinking chain, graph trace summary |
| **Evidence** | Scrollable research findings with source tier badges, relevance scores, and corroboration indicators |
| **Graph** | Interactive D3 force-directed transaction graph (colour-coded by entity role), GNN classification result, detected cycles list, and the **ONNX GraphPlayground** — edit node feature vectors and get live in-browser GNN inference |
| **Judge** | Evidence quality metrics (precision@10, corroboration %), claim graph with contradictions highlighted, counterfactual what-if bar chart, full search plan |
| **CAM** | Rendered Markdown preview with download buttons for `.md` and `.pdf` |
| **Notes** | Officer notes with full CRUD, tag filtering (OR logic), pin-to-top, and inline search |
| **Documents** | Upload and manage borrower documents |

### Visualisation Components

| Component | Description |
|-----------|-------------|
| **RiskGauge** | 220° donut arc gauge with centred percentage, colour transitions green → amber → red |
| **RiskWaterfall** | Stacked waterfall chart showing per-rule risk contribution from base to final score |
| **ClassRadar** | Spider chart of GNN entity class probabilities |
| **CounterfactualBar** | Horizontal bar chart of Δ risk for each what-if scenario |
| **EvidenceScatter** | Confidence × relevance scatter plot of research findings |
| **ForceGraph** | D3.js force-directed transaction network — drag nodes, zoom, hover for details |
| **GraphPlayground** | Edit node features (degree, amount, entity type) in a form → instant ONNX GNN classification in-browser (no backend) |

---

## API Reference

Base URL: `http://localhost:8000`

### Cases

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/cases/` | List all cases |
| `POST` | `/api/cases/` | Create a new case |
| `GET` | `/api/cases/{id}` | Full case detail (includes officer notes) |
| `DELETE` | `/api/cases/{id}` | Delete case + all files |
| `POST` | `/api/cases/{id}/documents` | Upload document (PDF, MD, JSON, TXT) |
| `GET` | `/api/cases/{id}/cam` | Download CAM (Markdown) |
| `GET` | `/api/cases/{id}/cam/pdf` | Download CAM (PDF) |
| `GET` | `/api/cases/{id}/graph` | Graph trace (nodes, edges, GNN, cycles) |
| `POST` | `/api/cases/{id}/notes` | Add officer note |
| `GET` | `/api/cases/{id}/notes` | List officer notes |
| `PATCH` | `/api/cases/{id}/notes/{nid}` | Update note (body, tags, pinned) |
| `DELETE` | `/api/cases/{id}/notes/{nid}` | Delete note |
| `GET` | `/api/cases/stats/dashboard` | Portfolio-wide statistics |
| `GET` | `/api/cases/compare/bulk?ids=a,b,c` | Multi-case comparison (max 5) |

### Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/run/{id}/stream` | SSE stream — runs full appraisal, emits live events |
| `POST` | `/api/run/{id}/sync` | Synchronous run — returns completed result |

### SSE Events

| Event | Payload |
|-------|---------|
| `log` | Progress text from each pipeline stage |
| `research_plan_ready` | Search queries planned by ResearchRouter |
| `evidence_scored` | Findings scored by EvidenceJudge |
| `claim_graph_ready` | Claims extracted + contradictions detected |
| `counterfactual_ready` | What-if scenarios generated |
| `complete` | Full decision trace |
| `error` | Pipeline failure details |

Interactive API docs available at [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI).

---

## Demo Cases

Three pre-built intelligence cases are **automatically seeded on server startup** with full documents, research caches, and pipeline results:

| Company | Verdict | Risk Score | Rules Fired | Key Signals |
|---------|---------|:----------:|:-----------:|-------------|
| **Sunrise Textiles Pvt Ltd** | ✅ APPROVE | 0.25 | 0 | CMR 3, DPD 0, clean ITC, capacity 78%, collateral 1.6× |
| **Apex Steel Components Ltd** | ⚠️ CONDITIONAL | 0.65 | 3 | CMR 6 (+0.10), DPD 45 (+0.10), ITC 33% excess (+0.15) |
| **Greenfield Pharma Industries** | ❌ REJECT | 1.00 | 9 | CMR 9, DPD 120, circular trading, criminal cases, capacity 25% |

Each demo case comes with parser-friendly documents, structured transaction data, and pre-shaped research caches — no live SearXNG or Ollama calls required to explore the full UI experience.

Additional demo payloads are available in `demo/seed/` for API-level testing.

---

## Test Suite

### Backend — 231 tests (pytest)

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short
```

Coverage spans: API CRUD, demo case manifest assertions, graph construction + GNN + cycle detection, trace schema v3 validation, SSE event ordering, officer notes CRUD/PATCH/DELETE, full case lifecycle, research agent filtering, rule engine completeness, counterfactual generation.

### Frontend — 37 tests (Vitest)

```bash
cd frontend && npm test
```

Coverage spans: chart rendering (RiskGauge, RiskWaterfall), modal interactions, health badge states, case list delete flow, notes CRUD UI, ONNX feature vector construction.

### E2E — Playwright

```bash
./scripts/start.sh          # Terminal 1
cd frontend && npm run e2e   # Terminal 2
```

---

## Project Structure

```
Intelli-Credit/
├── app/                          # FastAPI application
│   ├── main.py                   # App init, CORS, demo seeder, lifespan
│   └── api/
│       ├── cases.py              # Case CRUD, stats, compare, CAM, notes
│       ├── run.py                # SSE pipeline endpoint
│       └── autofetch.py          # Auto-fetch enrichment
│
├── services/                     # Core intelligence services
│   ├── pipeline.py               # 9-stage pipeline orchestrator
│   ├── agents/                   # Multi-agent research system
│   │   ├── orchestrator.py       # Agent coordinator
│   │   ├── research_agent.py     # SearXNG web researcher
│   │   ├── research_router.py    # LLM search query planner
│   │   ├── evidence_judge.py     # Evidence quality scorer
│   │   ├── claim_graph.py        # Claim extraction + contradiction detection
│   │   └── counterfactual.py     # What-if scenario generator
│   ├── cam/                      # CAM generation
│   │   ├── generator.py          # Markdown CAM
│   │   └── pdf_generator.py      # ReportLab PDF CAM
│   ├── graph/                    # Graph intelligence
│   │   ├── builder.py            # Transaction graph (NetworkX)
│   │   └── intelligence.py       # GNN + cycle detection
│   ├── reasoning/
│   │   └── rule_engine.py        # YAML v2 rule engine
│   ├── ingestor/                 # Document processing
│   │   ├── preprocess.py         # Document normalisation
│   │   ├── validator.py          # Regex fact extraction
│   │   └── provenance.py         # Source tracking
│   ├── lakehouse/
│   │   └── db.py                 # DuckDB ETL
│   ├── entity_resolution/
│   │   └── resolver.py           # RapidFuzz entity matching
│   └── cognitive/
│       └── engine.py             # DeepSeek-R1 reasoning wrapper
│
├── rules/                        # 10 YAML rule definitions (schema v2)
├── frontend/                     # React + Vite application
│   └── src/
│       ├── App.jsx               # Routes: /, /cases, /cases/new, /compare, /cases/:id
│       ├── components/           # 20+ UI components
│       │   ├── charts/           # RiskGauge, Waterfall, Radar, Scatter, ForceGraph, Playground
│       │   └── panels/           # KPI, Trace, Evidence, Graph, Judge, CAM, Notes, Docs, Timeline
│       └── services/
│           ├── api.js            # Centralised API client
│           └── gnn.js            # ONNX Runtime Web inference
│
├── demo/                         # Demo data + intelligence cases
├── tests/                        # 231 backend + 37 frontend tests
├── scripts/                      # Automation scripts
└── storage/                      # Runtime data (gitignored)
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://172.23.112.1:11434` | Ollama API endpoint |
| `SEARXNG_URL` | `http://localhost:8888` | SearXNG search endpoint |
| `VITE_PRESENTATION_MODE` | `0` | Set to `1` to hide sidebar + debug UI for screen-sharing |

### Models

| Model | Purpose | VRAM |
|-------|---------|------|
| `sjo/deepseek-r1-8b-llama-distill-abliterated-q8_0` | Primary reasoning, risk assessment, CAM narrative | ~8 GB |
| `qwen2.5:3b` | Agent coordination (Router, Judge, ClaimGraph) | ~2 GB |

### Research Cache

Results are cached at `storage/cache/research/<company>_v3_research.json`. Delete to force a fresh web search. Cache version `"3"` — older versions are automatically invalidated.

---

## Scripts

| Script | Description |
|--------|-------------|
| `./scripts/start.sh` | One-command startup (backend + frontend + WASM copy) |
| `./scripts/start.sh --no-frontend` | Backend only |
| `./scripts/run_acceptance.sh` | Run full test suite |
| `./scripts/judge_pack.sh` | Tests + showdown + scorecard → `reports/` |
| `python scripts/export_gnn_onnx.py` | Export GNN model to ONNX for browser inference |
| `python scripts/demo_intelligence_pack.py prepare\|verify\|cleanup` | Demo case lifecycle |

---

## Storage Layout

```
storage/
├── cases/{case_id}/
│   ├── meta.json            # Case metadata
│   ├── docs/                # Uploaded documents
│   ├── *_trace.json         # Decision trace (schema v3)
│   ├── *_research.json      # Research findings
│   ├── cam_*.md             # Markdown CAM
│   └── cam_*.pdf            # PDF CAM
├── cache/research/          # SearXNG result cache (v3)
└── lakehouse.duckdb         # Analytics database
```

---

## Why Fully Local?

Credit appraisal involves **highly sensitive financial data** — borrower tax returns, bank statements, CIBIL reports, promoter criminal records. Intelli-Credit is architected so that:

- **Zero data exfiltration** — no API calls to OpenAI, Anthropic, Google, or any cloud service
- **No billing surprises** — all ML inference runs on your own hardware via Ollama
- **Regulatory compliance** — data residency is trivially satisfied when data never leaves the machine
- **Reproducible** — deterministic rule engine + cached research = identical results on re-run
- **Air-gappable** — with models and research caches pre-loaded, the system can run without internet access

---

## License

Proprietary — Intelli-Credit is a private research prototype.
