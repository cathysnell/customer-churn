# Submission checklist

Track readiness against every FE Bar gate. Nothing is "done" until its **text-readable
execution evidence** is committed.

## Gate 1 — The build (required)

### Repo readability
- [ ] Repo is **public** (or GitHub connected on the form for a private EMU org).
- [ ] Repo link resolves and is readable as text by the validator.

### The six stages, each with committed text evidence
| # | Stage | Artifact | Text execution evidence |
|---|-------|----------|-------------------------|
| 1 | Lakeflow | ingestion pipeline | pipeline run log + row counts committed |
| 2 | Unity Catalog | DDL + grants | `SHOW GRANTS` / lineage query output committed |
| 3 | Lakebase | serving sync | query results / latency output committed |
| 4 | ML / Gen AI | model + serving | training metrics + real inference output committed |
| 5 | Genie Room | NL Q&A config | sample questions + returned SQL/results committed |
| 6 | Databricks App | business UI | app run log / served responses committed |

### Evidence rules (read carefully)
- [ ] Notebooks committed **with outputs visible** (not cleared).
- [ ] Evidence is **committed text**, not a screenshot or recording.
- [ ] No stage relies on source code alone to prove it ran.

### Data safety
- [ ] **Only synthetic or public data.** No real customer data / records /
      customer-identifying content anywhere in the repo or its history.
- [ ] `.gitignore` blocks stray data/credential files.

## Gate 2 — Presentation deck (required)
- [ ] Leads with the **business outcome**.
- [ ] Quantifies impact in the **buyer's KPIs**.
- [ ] Frames value for **both** the executive sponsor and the domain owner.
- [ ] Delivered as: shareable Google Slides ("Anyone with the link" = Viewer), **or**
      a PDF export, **or** an HTML deck (Drive link or committed to repo).

## Gate 3 — Conversation ID (optional)
- [ ] Build assistant conversation/session ID recorded (in case of a cheating flag).

---

## Verification discipline (how we work)
- Every code change is delegated to a coding sub-agent; polly never writes code.
- Every implementer PR is **cross-reviewed by a different vendor** before it's
  considered mergeable.
- Test / lint / gate output is re-run and confirmed, not taken on faith.
- The human merges PRs — polly does not.
