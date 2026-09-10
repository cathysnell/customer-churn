# Genie space — instructions / context

Paste this into the Genie space's **Instructions** (General instructions). It gives
Genie the business definitions and join rules it can't infer from schema alone.

---

## What this data is

A **freemium-to-Pro AI code editor** (Cursor archetype). We predict which Pro
subscribers will **churn** (cancel) so the retention team can intervene. Engagement
is measured monthly per user: coding hours, AI-suggestion acceptance rate, session
frequency, support load, and CRM contact.

## Key definitions

- **Churn** = an active subscriber on the first day of a month who **cancels during
  that month**. `churned = TRUE` marks that. Monthly churn rate is simply
  `AVG(churned)` over the at-risk rows for a month — the table only contains rows for
  months a user was actually at risk, so no denominator adjustment is needed.
- **Currently subscribed** = `is_currently_subscribed = TRUE` (subscription status is
  `active` or `downgraded`). Use this to restrict "who should we save" questions to
  live revenue.
- **Churn score** (`churn_score`, 0–1) = the model's churn **propensity**. It is a
  strong **ranking** of risk, **not a calibrated probability** — its absolute values
  run higher than the true ~3–5% monthly churn rate because the model up-weights the
  rare churn class. **Rank and compare with it; do not report it as "X% will churn."**
- **Risk band** (`churn_risk_band`) = `high` / `medium` / `low`, the actionable
  bucket derived from the score. Prefer this (and MRR at risk) over the raw score for
  business answers.
- **MRR at risk** = `SUM(mrr_usd)` over currently-subscribed users in a given risk
  band — the revenue the retention play is protecting.
- **The headline decline signal** is `coding_hours_trend_30d`: a ratio of this
  month's coding hours to last month's (1.0 = flat, < 1 = declining). Falling coding
  hours, falling `avg_acceptance_rate`, and falling `avg_session_frequency` all
  correlate with higher churn.

## Tables and how to join them

- **`dev_churn.gold.churn_serving`** — one row per user, current state: identity
  (`geo`, `plan`, `tier`, `persona`, `power_user_flag`), subscription
  (`subscription_status`, `is_currently_subscribed`, `mrr_usd`, `billing_period`),
  and the latest observed monthly engagement/label. **Default table for "who / how
  many / how much" questions about the current base.**
- **`dev_churn.gold.churn_predictions`** — one row per user: `churn_score`,
  `churn_risk_band`, `as_of_month`, and the `model_version` that produced it. **Join
  to `churn_serving` on `user_id`** to attach profile/revenue to a risk score.
- **`dev_churn.silver.churn_labels`** — one row per user **per month** (`month_start`
  grain). Use this, not the gold tables, for **history / trend-over-time** questions
  (churn rate by month, engagement trends).

Join key throughout is `user_id`. `churn_serving` and `churn_predictions` are 1:1 per
user; `churn_labels` is many-per-user (monthly).

## Answering guidance

- "At-risk / who should we contact" → `churn_predictions` filtered to `high` (optionally
  `medium`) risk, joined to `churn_serving` for profile, and usually restricted to
  `is_currently_subscribed = TRUE`.
- "Churn rate" or "trend" → `silver.churn_labels`, `AVG(CAST(churned AS INT))`, grouped
  by `month_start` (or `geo`, `persona`, …).
- Never present `churn_score` as a literal probability of churning; describe it as a
  risk score / ranking. When quantifying business impact, use counts by risk band and
  MRR at risk.
