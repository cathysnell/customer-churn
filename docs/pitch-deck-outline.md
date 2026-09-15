# Customer pitch deck — outline

A slide-by-slide outline for the **Retention Cockpit** pitch (the FE Bar "Customer
Skills" deliverable). Modeled on our live-FE-days deck's arc (cover → problem →
requirements → ROI anchor → demo → 3-part solution → live demo → cost/trust → why
Databricks → recap) and tightened with patterns from the **go/aapitch (Agentic
Analytics L100)** and **Value-pitch** templates.

**Audience (frame every slide for both):** the **executive sponsor** — a CRO who owns
churn & net revenue retention, and the CFO who owns retained ARR — *and* the **domain
owner** — the VP Data & Analytics / Head of AI/ML who has to run and trust it.

**Customer / archetype:** Anysphere (maker of the Cursor AI code editor) — a
freemium-to-Pro AI code editor whose **Pro-tier subscribers churn**.

> **All dollar/percentage baselines below are illustrative synthetic values** (see
> [`project-brief.md`](project-brief.md)) — label them as such on the slides. The
> *live* app figures (churn 3.25% vs the 4% target, $541K MRR at risk, 1,004 untouched
> high-risk subscribers, 26,568 active) come straight from the running build and are
> real outputs of the synthetic data.

## Design principles (pulled from the reference decks)
1. **Problem before product** — spend the first third on the pain; don't name the platform yet.
2. **ROI *before* the demo** — put the value numbers on the table so the audience knows what they're watching for.
3. **Three-part solution, memorable words** — Govern → Predict → Act (maps 1:1 to the three requirements).
4. **Show it, then explain it** — product screenshots with a one-line headline each, *then* the architecture.
5. **Humanize the protagonist** — name the account manager and the CRO; make the before/after land on a person.
6. **Open line = closing line** — bookend the deck with one repeatable sentence.
7. **Close to a next step, not an ask** — end on a concrete, low-commitment next move.
8. **Keep the customer deck tight (~15 slides); park depth in an INTERNAL appendix.**

---

## Slide-by-slide (target: 15 + appendix)

### 1 · Cover
- **Title line (the bookend):** *"Catch the churn before the renewal — not after."*
- Subtitle: Retention Cockpit for Pro-tier developer retention · 20-min brief + live demo.
- Sets protagonist (the revenue team) and format.

### 2 · The problem, in the CRO's words
- Pro-tier churn is running **~4.7% monthly** *(illustrative)* and retention is **reactive** — the business sees a lapse only after it hits the revenue number.
- The signals that predict it — **falling coding hours, dropping AI-suggestion acceptance, thinning session frequency** — are tracked but **siloed from the CRM** that could act on them.
- Humanize: "By the time *Maya* (CRO) sees the churn in the board deck, the developer already cancelled."

### 3 · The requirement (sets the evaluation criteria)
Three numbered non-negotiables — they map 1:1 to the three solution builds:
- **01 · A daily churn signal per Pro user** — not a quarterly model refresh.
- **02 · Governed & safe** — one source of truth, no PII sprawl, numbers the CFO can trust.
- **03 · Act inside the motion** — the signal must drive CRM outreach, not die in a dashboard.

### 4 · The outcomes we defend (ROI anchor — before the demo)
- **Hold Pro monthly churn < 4.0%** (from ~4.7% — a **−15%** relative cut). *Live: 3.25%, under target.*
- **+22% CRM reactivation** (8.0% → 9.8%) *(illustrative)*.
- **≈ $2.58M annual impact** *(illustrative)* = ARR × NRR lift + churn prevention × base × LTV.
- Frame for **CRO** (churn, NRR) **and CFO** (retained ARR, LTV) explicitly.

### 5 · Demo — Executive Overview *(screenshot + headline)*
- Headline: **"Are we winning against the 4% target?"** — churn vs target, MRR at risk by band, projected impact, plus a **⚡ Genie-written "so what"** summary that refreshes weekly.
- Point: the exec sees the state of retention in one screen, in governed numbers.

### 6 · Demo — Retention Worklist *(screenshot + headline)*
- Headline: **"1,004 high-value subscribers are high-risk with zero outreach — served live from Lakebase."**
- Point: the daily signal becomes a ranked, operational work queue for the account manager (name them — e.g. "Sam").

### 7 · Demo — Subscriber detail → the closed loop *(screenshot + headline)*
- Headline: **"One click logs outreach — and the subscriber drops off the queue instantly."**
- Shows the risk drivers, the **Agent-Bricks-drafted** re-engagement message, and *Log outreach* → live queue update. This is the closed loop.

### 8 · The solution (three moves — cumulative reveal)
- **Govern → Predict → Act**, mapped to requirements 01/02/03. Introduce the map here; the next three slides each take one. *(Use `docs/architecture.svg`.)*

### 9 · Build 1 · Predict — governed data, scored daily *(→ Req 01)*
- Lakeflow ingests behavioral + subscription + CRM signals → Unity Catalog medallion → **MLflow churn model scores every Pro user daily**, written back as a governed table. Governed metric views are the single semantic layer.

### 10 · Build 2 · Serve & surface — live, not batch *(→ Req 02)*
- **Before:** yesterday's batch extract in a spreadsheet. **After:** the cockpit reads **Lakebase** (low-latency serving) so the worklist is current. Same governed metric views feed the app — the CFO's number and the analyst's number are the *same* number.

### 11 · Build 3 · Act — Genie + Agent Bricks, governed *(→ Req 03)*
- Ask retention questions in plain language (**Genie** over the governed views); act with an **Agent-Bricks-drafted** message; logging outreach writes to the governed system of record and updates the queue live. *(Use `docs/process-flow.svg`.)*

### 12 · Live demo (scripted)
- (a) **Overview:** under the 4% target — but risk is concentrated in the high-value band.
- (b) **Worklist:** open the top at-risk subscriber → review the AI draft → *Log outreach* → watch them leave the queue.
- (c) **Ask Genie:** "Which regions are trending worse this month?" → governed answer, matches the dashboard.

### 13 · Trust & cost — why the CFO can sign off
- **One governed source of truth:** app and Genie read the *same* metric views, so numbers can't diverge.
- **No PII sprawl:** the app reads governed/serving tables; synthetic data throughout this build.
- **Bounded, attributable AI:** Genie + Agent Bricks run on the governed platform, not a bolt-on.

### 14 · Why Databricks (earn it late)
- One platform, one governance layer end to end: **Lakeflow → Unity Catalog → Lakebase → MLflow → Genie → Databricks Apps** — the app *is* deployed on it.
- **vs. the alternative:** stitching a point-solution CRM add-on + a separate warehouse + a separate model host means three governance boundaries and diverging numbers. Here it's one.

### 15 · Recap + next step (close the arc)
- The four numbers again: **< 4% churn · +22% reactivation · ≈ $2.58M impact · 1,004 saves in the queue today.**
- Bookend line: *"Catch the churn before the renewal — not after."*
- **Concrete CTA:** a **2-week retention MVP** on your own data — wire one behavioral source + stand up the cockpit against your Pro base.

---

## Appendix (INTERNAL — mark clearly; drop before sending externally)
- Architecture deep-dive (the closed loop; Delta↔Lakebase system-of-record rule).
- The roadmap items: **CRM integration** (the dotted line in `process-flow.svg` — Salesforce/HubSpot hand-off) and the **PG→Delta outreach sync** (recompute `crm_touches_30d` in the lakehouse).
- FE Bar mapping: the six mandated stages → where each shows up in the demo.
- Data-safety note: illustrative synthetic figures, labeled; no real customer data.

## Assets to drop in
- **Slide 8 (solution):** `docs/architecture.svg`.
- **Slide 11 / demo (closed loop):** `docs/process-flow.svg`.
- **Slides 5–7:** screenshots of the live app (Overview, Worklist, Subscriber detail).
