# Stage 5/6 — Overview "So what?" Genie narrative (execution evidence)

The Overview "So what?" box now carries a **Genie-authored qualitative narrative**,
cached ~weekly in **Lakebase** (`public.app_narrative`), with the authoritative
figures still rendered from the governed warehouse endpoints (never Genie's numbers).
Captured 2026-09-12 on `fevm-serverless-stable-yuzk83`, app SP
`1768cda0-b24e-493f-8b2f-16fb8b8eda3a`, Genie space `01f1ad360e121f099e3070de938cd8cb`.

## 1. Lakebase cache table created + granted (approved workspace write)

Applied `serving/app_narrative.sql` to the Lakebase Postgres (`databricks_postgres`)
as the instance owner (psql + `databricks postgres generate-database-credential`):

```
CREATE TABLE ; COMMENT ; GRANT               (all OK)

Table "public.app_narrative"
  cache_key    text        not null   PRIMARY KEY
  body         text        not null
  generated_at timestamptz not null   DEFAULT now()
  source       text        not null   CHECK (source IN ('genie','fallback'))

grants → 1768cda0-…  =  INSERT, SELECT, UPDATE   (verified)
```

The SP's Postgres role already existed (from the Stage-6 do-now grants), so only the
per-table grant was added.

## 2. Genie live probe — the prompt returns a real qualitative narrative

Posed `SO_WHAT_PROMPT` to the live Genie space (start-conversation → poll → message).
Genie treated it as an analysis request: it ran a governed `MEASURE()` query AND
returned two text attachments — a **clarifying question** and the **actual narrative**.

Raw narrative attachment (verbatim, markdown as returned):

> Current Pro-tier churn risk is concentrated among **non-power users** and the
> **high-risk** segment, where engagement is weakest: they show the lowest acceptance,
> the fewest sessions, and declining coding activity versus lower-risk and power users.
> The single most important retention focus this month is to **re-engage high-risk
> non-power users** by driving product usage and habit formation, since stronger
> engagement consistently aligns with lower churn risk across all 5 rows shown.

## 3. Bug the live probe caught (invisible to synthetic tests)

`extractText` (used by the Ask tab) returns the **first** text attachment — which here
was the clarifying question *"Would you prefer to see the current churn situation broken
down by other segments…?"*, NOT the narrative. Fixes:

- New `pickNarrativeText()` — takes the longest text attachment that isn't a question
  (falls back to any text, then message content). `askGenieNarrative()` uses it and
  skips the query-result fetch. `extractText`/the Ask tab are unchanged.
- `cleanNarrative()` now also strips markdown emphasis, removes a trailing
  "…across/in N rows shown" data-reference artifact, and keeps the first two sentences.
- `SO_WHAT_PROMPT` tightened: "do not reference the query, the underlying data, or the
  number of rows. Reply with the narrative only."

Cleaned output actually rendered (the real attachment run through the real code):

> Current Pro-tier churn risk is concentrated among non-power users and the high-risk
> segment, where engagement is weakest: they show the lowest acceptance, the fewest
> sessions, and declining coding activity versus lower-risk and power users. The single
> most important retention focus this month is to re-engage high-risk non-power users
> by driving product usage and habit formation, since stronger engagement consistently
> aligns with lower churn risk.

## 4. Cache SQL validated against the live table (PREPARE/EXECUTE)

Ran the exact parameterized statements from `app/server/lakebase.ts`:

```
insert            → INSERT 0 1
read              → first body  | genie
upsert-update     → INSERT 0 1  (ON CONFLICT DO UPDATE)
read again        → second body | fallback
bad source        → ERROR: violates check constraint "app_narrative_source_check"
cleanup (delete)  → DELETE 1
final count       → 0
```

Probe row deleted; the table is empty, so the first Overview load on the deployed app
performs the genuine synchronous Genie generation + SP-authenticated cache write.

## 5. Remaining (post-merge)

Deploy the app from merged `main`, then verify end-to-end live:
`GET /api/overview/so-what` → `source:"genie"` with a fresh `generatedAt`, a cache row
written by the SP, and the "⚡ Powered by Genie · Updated <date>" stamp on the box.
Until deploy, the box shows the templated fallback (no pill) — safe and correct.
