# Genie knowledge store — synonyms, entity matching, value aliases

The Genie space's **knowledge store** (per-column synonyms + entity matching) is
UI-only — it isn't part of the `serialized_space` you'd normally version, so it's
captured only by `databricks genie get-space <id>`. This file is the reviewable
source of record: enter it in the space UI by hand, keep it in sync here.

It maps 1:1 to the column edit dialog: **Configure → Sources → click a table →
click a column (pencil)**. Each column dialog has **Synonyms** (a text box) and,
under **Advanced**, two toggles — **Format assistance** (samples example values,
read-only) and **Entity matching** (Genie matches a user's word to a real value in
that column; max 120 string columns per space).

> There is **no free-text "value dictionary" box**. Entity matching is a toggle that
> works off the column's *actual* values. For words the data does **not** literally
> contain (e.g. "Europe" for `EMEA`), use the **Instructions** aliases in the last
> section — those live in [`instructions.md`](instructions.md).

---

## 1. Synonyms (per column)

Add these comma-separated in each column's **Synonyms** box. Covers the fields a
business user is likely to name. Tables: `S` = `gold.churn_serving`,
`P` = `gold.churn_predictions`, `L` = `silver.churn_labels`.

| Table | Column | Synonyms |
| --- | --- | --- |
| P | `churn_score` | risk score, churn propensity, propensity, likelihood to churn |
| P | `churn_risk_band` | risk band, risk level, risk tier, churn risk |
| S | `mrr_usd` | MRR, revenue, monthly recurring revenue, monthly revenue |
| S | `is_currently_subscribed` | active subscriber, paying, paying customer, subscribed |
| S | `coding_hours_trend_30d` | engagement trend, usage trend, coding trend |
| S | `avg_acceptance_rate` | AI acceptance, suggestion acceptance, acceptance rate |
| S | `avg_coding_hours` | coding hours, usage, activity |
| S | `avg_session_frequency` | session frequency, sessions, logins |
| S | `power_user_flag` | power user |
| S | `crm_touches_30d` | outreach, CRM touches, campaigns, contacts |
| S | `support_tickets_30d` | support tickets, tickets, support load |
| S | `persona` | user type, segment |
| S | `geo` | region, geography |
| S | `billing_period` | billing cycle, billing |
| S | `subscription_status` | account status, subscription state |
| S / L | `tenure_months` | tenure, account age |
| S/P/L | `user_id` | user, customer, developer, account |

---

## 2. Entity matching — toggle ON (per column)

Turn **Entity matching** ON for these low-cardinality **string** columns, so Genie
resolves a user-typed value to the right column. (Format assistance is ON by default
and shows the sampled values; leave it on.) Distinct values pulled 2026-09-10:

| Table | Column | Values (what Genie will match) |
| --- | --- | --- |
| S | `geo` | `ANZ`, `APAC`, `EMEA`, `LATAM`, `MEA`, `NA` |
| P | `churn_risk_band` | `high`, `medium`, `low` |
| S | `subscription_status` | `active`, `canceled`, `churned_after_reactivation` |
| S | `persona` | `freelancer`, `individual_dev`, `startup_founder`, `student`, `team_lead` |
| S | `plan` | `pro_annual`, `pro_monthly`, `pro_team_monthly` |
| S | `billing_period` | `annual`, `monthly` |

**Skip `tier`** — single value (`pro`), nothing to match; don't spend an
entity-matching slot on it.

---

## 3. Value aliases → put in Instructions (not the UI)

Entity matching only matches words the data literally contains. These are the
business terms that *don't* appear as values, so they go in
[`instructions.md`](instructions.md) as explicit mappings:

- **Region words** → `geo`: "Europe" → `EMEA`; "North America" / "US" / "USA" → `NA`;
  "Asia" / "Asia-Pacific" → `APAC`; "Latin America" → `LATAM`; "Middle East" /
  "Africa" → `MEA`; "Australia" / "New Zealand" / "Oceania" → `ANZ`.
- **Risk words** → `churn_risk_band`: "at risk" / "at-risk" / "flight risk" /
  "likely to churn" → `high`.
- **Lapsed words** → `subscription_status`: "lapsed" / "cancelled" / "churned" →
  `canceled`.
- **Persona words** → `persona`: "founder" → `startup_founder`; "solo dev" /
  "individual" → `individual_dev`; "lead" / "manager" → `team_lead`.
- **Plan words** → `plan`: "team plan" → `pro_team_monthly`; "annual plan" →
  `pro_annual`.

---

## Applying / re-syncing

1. Enter §1 and §2 in the space UI (per-column dialog).
2. The §3 aliases ship in `instructions.md` — paste that into the space's Instructions.
3. After editing in the UI, capture the config back:
   `databricks genie get-space <space_id> -p fevm-serverless-stable-yuzk83` and diff
   against this file so the two don't drift.
