# Feature Access Matrix — Intelli-Credit v3.0

> **Phase 5 complete.** Every backend API endpoint is now reachable from the
> frontend UI. This document maps each backend endpoint to its UI entry point.

---

## Cases

| Backend Endpoint | Method | UI Access | Component |
|---|---|---|---|
| `/api/cases/` | GET | Cases list page (auto-loaded on mount) | `CaseList.jsx` |
| `/api/cases/` | POST | "New Case" form | `CaseCreate.jsx` |
| `/api/cases/{id}` | GET | Case detail page (auto-loaded) | `CaseDetail.jsx` |
| `/api/cases/{id}` | DELETE | "🗑 Delete Case" button *(header)* + "🗑 Delete" per-row button | `CaseDetail.jsx`, `CaseList.jsx` |

---

## Documents

| Backend Endpoint | Method | UI Access | Component |
|---|---|---|---|
| `/api/cases/{id}/documents` | POST | Document upload form (Overview tab) | `CaseDetail.jsx` |
| `/api/cases/{id}/cam` | GET | "⬇ Download CAM (.md)" link (CAM tab) | `CaseDetail.jsx` |

---

## Pipeline Runs

| Backend Endpoint | Method | UI Access | Component |
|---|---|---|---|
| `/api/run/{id}/stream` | GET (SSE) | "▶ Run Analysis" button (Run tab) | `CaseDetail.jsx` |
| `/api/run/{id}` | POST (sync) | "▶ Run (Sync)" fallback button (shown after SSE error) | `CaseDetail.jsx` |

---

## Notes 2.0

| Backend Endpoint | Method | UI Access | Component |
|---|---|---|---|
| `/api/cases/{id}/notes` | GET | Notes tab (auto-loaded when tab opens) | `CaseDetail.jsx` |
| `/api/cases/{id}/notes` | POST | "Save Note" / "Update Note" form in Notes tab | `CaseDetail.jsx` |
| `/api/cases/{id}/notes/{nid}` | PATCH | "✏ Edit" button → form → "Update Note" | `CaseDetail.jsx` |
| `/api/cases/{id}/notes/{nid}` | DELETE | "🗑" (trash) button per note → ConfirmModal | `CaseDetail.jsx` |

---

## Health

| Backend Endpoint | Method | UI Access | Component |
|---|---|---|---|
| `/api/health` | GET | Health badge in navbar (polling every 30 s) | `App.jsx` |
| `/health` | GET | Same badge (alias endpoint) | `App.jsx` |

---

## Notes

### Notes 2.0 — Tag & Pin features
- **Tags**: up to 5, lowercase-normalised, deduplicated. Filter bar in Notes tab supports OR-logic tag chip selection.
- **Pinned**: toggle in add/edit form; pinned notes always sort to the top of the notes list.
- **Updated at**: displayed as "(edited)" indicator when `updated_at > created_at`.
- **Backward-compat**: legacy notes without `tags`/`pinned`/`updated_at` fields are transparently normalised on read.

### UI shared components
- `ConfirmModal.jsx` — shared danger/safe confirmation modal used by case delete and note delete.
- `frontend/src/services/api.js` — centralised async API client; all HTTP calls go through this module.

---

## Test coverage

| Layer | Runner | Test files | Tests |
|---|---|---|---|
| Backend unit | pytest | `tests/unit/` | ~70 |
| Backend integration | pytest | `tests/integration/` | ~130 |
| **Backend Phase 5** | pytest | `test_phase5_notes.py`, `test_phase5_e2e_flow.py` | **22** |
| Frontend component | Vitest | `src/test/*.test.jsx` (4 files) | **24** |
| Frontend E2E smoke | Playwright | `e2e/judge_demo.spec.js` | 11 |

**Total backend (pytest): 197+ tests**  
**Total frontend (Vitest): 24 unit tests** (Playwright requires live servers — see `README`)
