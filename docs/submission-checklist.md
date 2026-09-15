# Submission checklist

Track readiness against every FE Bar gate. Nothing is "done" until its **text-readable
execution evidence** is committed.

## Gate 1 — The build (required)

### Repo readability
- [x] Repo is **public** — <https://github.com/cathysnell/customer-churn> (verified PUBLIC).
- [x] Repo link resolves and is readable as text by the validator.

### The six stages, each with committed text evidence
| # | Stage | Artifact | Committed text execution evidence |
|---|-------|----------|-------------------------|
| 1 | Lakeflow | ingestion pipeline | ✅ `evidence/lakeflow-ingest-run.md` (run log + row counts) |
| 2 | Unity Catalog | DDL + grants | ✅ `evidence/unity-catalog-governance.md` (grants / lineage output) |
| 3 | Lakebase | serving sync | ✅ `evidence/lakebase-serving-run.md` + `app-lakebase-donow.md` (query results / latency) |
| 4 | ML / Gen AI | model + serving | ✅ `evidence/ml-churn-run.md` (training metrics + inference output) |
| 5 | Genie Room | NL Q&A config | ✅ `evidence/genie-space.md` (sample questions + returned SQL/results) |
| 6 | Databricks App | business UI | ✅ `evidence/app-served-responses.txt`, `app-genie-sowhat.md`, `app-lakebase-seam.md`, `app-scaffold.md` |

### Evidence rules (read carefully)
- [x] Execution artifacts committed **with outputs visible** (logged run output / query
      results / served responses — not cleared).
- [x] Evidence is **committed text**, not a screenshot or recording.
- [x] No stage relies on source code alone to prove it ran.

### Data safety
- [x] **Only synthetic or public data.** No real customer data / records /
      customer-identifying content anywhere in the repo or its history.
- [x] `.gitignore` blocks stray data/credential files (`data/` fully ignored).

## Gate 2 — Presentation deck (required)
- [ ] Leads with the **business outcome**.
- [ ] Quantifies impact in the **buyer's KPIs**.
- [ ] Frames value for **both** the executive sponsor and the domain owner.
- [ ] Delivered as: shareable Google Slides ("Anyone with the link" = Viewer), **or**
      a PDF export, **or** an HTML deck (Drive link or committed to repo).

> **Status:** a slide-by-slide **outline** is drafted at
> [`docs/pitch-deck-outline.md`](pitch-deck-outline.md) (modeled on the live-FE-days deck
> + the go/aapitch and Value-pitch templates). The **deck itself is not yet built** — this
> gate stays open until the slides exist and are shared.

## Gate 3 — Conversation ID (optional)
- [ ] Build assistant conversation/session ID recorded (in case of a cheating flag).

---

## Verification discipline (how we work)
- Every code change ships via a branch + PR; the orchestrator opens PRs, never merges.
- Every implementer PR is **cross-reviewed by a different vendor** before it's
  considered mergeable.
- Test / lint / gate output is re-run and confirmed, not taken on faith.
- **The human merges PRs** — the automation does not.
- Infra/library capabilities are verified against docs/live probes; execution evidence
  comes from probing the real system, never a synthetic pass.
