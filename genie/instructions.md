# Genie space — instructions / context

Paste this into the space's **Instructions**. It is deliberately short: most of the
semantics now live in structural layers Genie reads directly (the curation hierarchy
puts text instructions **last**). Prefer, in order:

1. **Metric views** — `dev_churn.gold.churn_metrics_current` (one row/user: risk bands,
   MRR at risk, engagement) and `dev_churn.gold.churn_metrics_monthly` (churn rate and
   trends over time). Certified measures/dimensions; use these for aggregates.
2. **Trusted functions** — `dev_churn.gold.at_risk_users(min_score)` and
   `dev_churn.gold.untouched_at_risk_users(band)` for the common row-level asks.
3. **Foreign keys** — `churn_predictions.user_id → churn_serving.user_id` is declared
   in UC, so joins across the two are known; both are 1 row per user.

## What this data is

A freemium-to-Pro **AI code editor** (Cursor archetype). We predict which Pro
subscribers will **churn** (cancel) so the retention team can intervene. Engagement is
measured monthly per user: coding hours, AI-suggestion acceptance rate, session
frequency, support load, CRM contact.

## Definitions that aren't in the metrics layer

- **Churn** = an active subscriber on the first of a month who cancels during it
  (`churned = TRUE`). Monthly churn rate = `AVG(churned)` — use the *Churn rate*
  measure on `churn_metrics_monthly`.
- **Currently subscribed** = `is_currently_subscribed = TRUE` (status `active` or
  `downgraded`). Restrict "who should we save" questions to these.
- **The decline signal**: falling `coding_hours_trend_30d` (<1 = declining), acceptance
  rate, and session frequency all track higher churn.

## Vocabulary — map these words to column values

Users say business terms the data doesn't store literally. Resolve them:

- **Regions** (`geo`): "Europe" → `EMEA`; "North America" / "US" / "USA" → `NA`;
  "Asia" / "Asia-Pacific" → `APAC`; "Latin America" → `LATAM`; "Middle East" /
  "Africa" → `MEA`; "Australia" / "New Zealand" / "Oceania" → `ANZ`.
- **Risk** (`churn_risk_band`): "at risk" / "at-risk" / "flight risk" / "likely to
  churn" → `high`.
- **Lapsed** (`subscription_status`): "lapsed" / "cancelled" / "churned" → `canceled`.
- **Personas** (`persona`): "founder" → `startup_founder`; "solo dev" / "individual"
  → `individual_dev`; "lead" / "manager" → `team_lead`.
- **Plans** (`plan`): "team plan" → `pro_team_monthly`; "annual plan" → `pro_annual`.

(Values the data *does* contain — the region codes, band names, personas themselves —
are handled by per-column entity matching; see [`knowledge_store.md`](knowledge_store.md).)

## The one rule to always follow

`churn_score` is a **risk ranking, not a calibrated probability** — the model
up-weights the rare churn class, so scores run well above the true ~3–5% monthly rate.
**Never report it as "X% of users will churn."** Quantify risk with **risk-band counts**
and **MRR at risk** (the *MRR at risk* measure sliced by *Risk band*), and rank
individuals by score. There is intentionally no "churn probability" measure to report.
