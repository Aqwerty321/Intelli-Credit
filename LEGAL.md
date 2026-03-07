# LEGAL.md — Crawling Policies & Data Governance

> Intelli-Credit crawling, scraping, and data handling policies.

---

## 1. Web Crawling Policies

### 1.1 General Principles
- All web crawling is performed for **legitimate credit assessment research** only.
- Comply with each website's `robots.txt` directives. Do not crawl disallowed paths.
- Respect `Crawl-delay` directives. Default minimum delay: **2 seconds** between requests to the same domain.
- Honor `noindex` and `nofollow` meta tags.

### 1.2 Rate Limiting
| Source Category | Max Requests/Minute | Notes |
|---|---|---|
| Government portals (MCA, e-Courts, GST) | 10 | Respectful crawling; cache aggressively |
| News websites | 20 | Respect paywall boundaries |
| Corporate websites | 15 | Avoid overwhelming small hosting |
| General web | 30 | Standard politeness |

### 1.3 Anti-Bot Evasion — Ethical Boundaries
- Use realistic User-Agent strings. Do not impersonate specific users.
- Proxy rotation is permitted for IP diversity but **not** to circumvent explicit bans.
- CAPTCHA solving: only for publicly accessible content. Do not bypass authentication or paywalls.
- If a site explicitly blocks automated access, **respect the block** and document the limitation.

### 1.4 Prohibited Actions
- Never scrape private/authenticated content without explicit authorization.
- Never scrape personally identifiable information (PII) of individuals unrelated to the credit assessment.
- Never access internal/admin pages, APIs, or endpoints not intended for public use.
- Never store or redistribute copyrighted content beyond fair use for credit analysis.

---

## 2. Data Governance

### 2.1 Data Classification
| Classification | Examples | Handling |
|---|---|---|
| **Confidential** | Bank statements, CIBIL reports, GST returns | Encrypted at rest; never transmitted; local processing only |
| **Internal** | Extracted financial metrics, risk scores, CAM drafts | Access controlled; audit logged |
| **Public** | News articles, MCA filings, court records | Can be cached; cite sources |

### 2.2 Data Sovereignty
- **All data stays on the local host.** No cloud uploads, no external API calls that transmit raw financial data.
- External API calls (web search, URL fetching) transmit only search queries, never raw document content.
- Model inference is **100% local**. No data sent to external LLM providers.

### 2.3 Retention Policy
- **Raw input documents** (`storage/raw/`): Retained for the duration of the assessment plus 90 days.
- **Processed artifacts** (`storage/processed/`): Retained for 1 year.
- **Logs** (`logs/`): Retained for 90 days, then rotated.
- **Generated CAMs**: Retained per institutional policy (recommended: 7 years for regulatory compliance).

### 2.4 Audit Trail
- Every automated decision, extraction, and web lookup writes a provenance record to the local lakehouse (DuckDB).
- Provenance records include: source file, page, byte offset, extraction method, confidence, agent ID, timestamp.
- Audit logs are immutable once written (append-only tables).

---

## 3. Regulatory Compliance

### 3.1 RBI Guidelines
- System design aligns with RBI Master Directions on Credit Risk Management (2025/2026).
- Algorithmic decisions include deterministic neuro-symbolic traces (PyReason + IBM LNN) for auditability.
- The system supports the FREE-AI Committee's requirements for transparency, ethical alignment, and risk mitigation.

### 3.2 Data Protection
- No personal data is shared with third parties.
- Credit officers access the system through local interfaces only.
- All sensitive data is processed in-memory where possible; disk writes use encrypted storage if available.

---

## 4. Open Source Licenses in Use

| Component | License | Notes |
|---|---|---|
| GLM-OCR | MIT / Apache 2.0 | Model weights: MIT; Code: Apache 2.0 |
| DeepSeek-R1 | MIT | Model weights |
| llama.cpp | MIT | Inference runtime |
| DuckDB | MIT | Analytics engine |
| LanceDB | Apache 2.0 | Vector store |
| PyReason | BSD 3-Clause | Logic engine |
| IBM LNN | Apache 2.0 | Neural-symbolic |
| Crocodile | Apache 2.0 | Entity resolution |
| Firecrawl-Simple | AGPL-3.0 | Self-hosted web extraction |
| PyTorch Geometric | MIT | Graph neural networks |

---

*Last updated: 2026-03-07*
