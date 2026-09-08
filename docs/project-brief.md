# Project brief — industry & customer problem

> **STATUS: FILLED from customer use-case inputs.** Source: Databricks "Enrich"
> customer use-case entry for **Anysphere** (maker of the Cursor AI code editor).
> Selected build: **Developer Behavioral Analytics Platform for Retention and
> Churn Prediction.** Any number not present in the source inputs is marked
> _(assumption — confirm)_ so it is never mistaken for a given fact.

## Industry
**Developer tools / B2B SaaS (AI-assisted software development).** Sub-segment:
freemium-to-Pro subscription IDE with a Pro tier. Customer archetype: **Anysphere
(Cursor).**

## The customer problem
Anysphere sells a Pro-tier subscription to an AI code editor. **Pro-tier
subscribers churn**, and retention is currently reactive — there is no unified,
daily signal that predicts *which* Pro users are about to lapse in time to
intervene. Behavioral signals that predict churn (active coding hours, AI
suggestion acceptance rate, session frequency) are tracked but siloed from the
CRM motion that would act on them.

Concretely: **keep Pro-tier monthly churn below the 4% target** by scoring every
Pro user daily for churn propensity and triggering personalized re-engagement
before they lapse — instead of noticing churn only after it shows up in the
revenue numbers.

Anchored to the initiatives named in the use case: **CRM-Driven Behavioral
Retention Program**, **Feature-Led Retention and Stickiness**, and
**Freemium-to-Pro Upsell Motion**.

## The business outcome (deck leads with this)
A unified behavioral analytics platform that turns raw developer-activity signals
into a **daily churn-propensity score per Pro user**, feeds those scores into
**personalized CRM re-engagement campaigns**, and holds **monthly Pro churn under
4%** while lifting reactivation — so revenue leaders manage retention proactively
on a KPI dashboard rather than reacting to lapsed subscriptions.

## KPIs / quantified impact
From the use case:
- **Primary KPI — Pro-tier monthly churn rate.** Target: **below 4%** (given).
  Benchmark improvement: **−15% churn rate** (given; LOE **Low**). Read these as
  compatible framings, not a contradiction: **<4%** is the absolute target level;
  **−15%** is the *relative* reduction the pattern is benchmarked to deliver
  (i.e. this initiative is expected to cut churn ~15% vs. baseline, and the
  program's target floor for Pro monthly churn is 4%). The implied baseline is
  therefore **~4.7% monthly** if a 15% cut lands at 4% _(assumption — confirm the
  baseline)_.
- **CRM-driven reactivation rate improvement.** Target: **+22%** (given in the
  use-case evidence note).
- **Power user daily engagement threshold** — a daily-engagement bar used to
  define/segment power users (used as a model feature and a stickiness KPI).
- Baseline → target: exact baseline churn and baseline reactivation rate are
  **not stated** in the inputs _(assumption — confirm; needed for the deck's
  before/after)_.

## ROI model (given)
- **Pattern:** Customer Revenue Expansion & Churn Prevention.
- **ROI template (verbatim):**
  `Annual_Impact = ARR × NRR_Improvement% + Churn_Prevention × Customer_Base × LTV`
- Inputs still needed to compute a dollar figure for the deck: **ARR**,
  **NRR_Improvement%**, **Churn_Prevention** (rate), **Customer_Base**, **LTV**
  _(assumption — none of these values are in the inputs yet; confirm or we label
  the deck's dollar impact as illustrative synthetic)_.

## Personas
Primary (from the use case):
- **Chief Revenue Officer (executive sponsor / signs)** — owns churn and net
  revenue retention; cares about Pro churn <4% and reactivation lift.
- **CFO & Head of Finance** — cares about retained ARR, LTV/CAC, forecast
  reliability.

Also relevant (from the use case): **CMO** (campaign motion), **VP Data &
Analytics** and **Head of AI/ML** (platform + model owners, day-to-day domain
owners), **CTO**.

## The dataset
- **Source:** **Synthetic, generated in-repo.** Rationale: this is developer
  behavioral + subscription data; per FE Bar data-safety rules we use **no real
  customer data**. Anysphere/Cursor product telemetry is not public, so we
  synthesize a realistic developer-activity + subscription-lifecycle dataset.
- **Signals to synthesize (named in the use case):** active coding hours, AI
  suggestion acceptance rate, session frequency, plus subscription lifecycle
  (signup, tier, renewals, cancellation) and CRM campaign touches/outcomes.
- **Realism levers:** correlate declining coding hours / falling AI-acceptance /
  dropping session frequency with higher churn; encode geographies (the use case
  calls out behavioral patterns evolving "across geographies"); include power
  users above the daily-engagement threshold.
- **Schema / volume:** _(assumption — to be specified in the data-generation
  task; propose ~N users over M months.)_
- **Data safety:** synthetic only; zero real customer data; enforced by
  `.gitignore` and reiterated in the requirements doc.

### Data assets to model (from the use case)
**Mission-critical (MC) — the churn-prediction core:**
- **A03 — Subscription plans & billing history** (source systems: ERP/Billing,
  Revenue Management, Data Warehouse) → tenure, payment history, downgrades.
- **A06 — Raw product usage events & telemetry** (Event Bus, Product Analytics,
  Data Lake) → the behavioral signal: coding hours, AI-acceptance, session
  frequency. This is the Structured Streaming / Lakeflow ingest source.
- **A07 — Feature adoption & activation metrics** (Analytics Marts, Feature
  Store, Data Warehouse) → stickiness-feature adoption.
- **A14 — Support tickets, chat logs & CSAT** (Support Platform, Chat, ITSM,
  Data Warehouse) → support friction as a churn signal.

**Value-add (VA) — enrichment for targeting/outreach:** persona, entitlements,
marketing saturation, and unified identity — to tailor offers and pick the
outreach channel. _(The use case references VA assets in the rationale but does
not enumerate them individually; the four above are the explicitly listed MC
assets.)_

**Selection rationale (from the use case):** MC assets capture tenure, payment
and downgrade history plus adoption of stickiness features and support friction
to predict churn; VA assets enrich with persona, entitlements, marketing
saturation and unified identity to tailor offers and outreach channel.

**Why this use case matches the pattern (from the use case):** both focus on
predicting churn risk at the user/account level using behavioral signals (coding
hours, AI-suggestion acceptance) to orchestrate retention plays — ingesting
activity signals to score churn probability and trigger interventions.

## Product / stage mapping (use-case products → FE Bar mandated journey)
The use case names these products: **Lakebase, MLflow, Lakeflow Connect,
Databricks SQL, Agent Bricks, Structured Streaming.** The FE Bar program mandates
this integrated six-stage journey. Mapping:

| FE Bar mandated stage | How this build satisfies it | Use-case products used |
| --- | --- | --- |
| **Lakeflow (ingest)** | Ingest raw synthetic behavioral + subscription + CRM events | **Lakeflow Connect**, **Structured Streaming** (daily/near-real-time signal flow) |
| **Unity Catalog (govern)** | Govern the behavioral tables, features, and model assets | Unity Catalog (mandated; implicit governance layer) |
| **Lakebase (serve)** | Operational store for real-time/daily per-user churn state | **Lakebase** |
| **ML / Gen AI (intelligence)** | Daily churn-propensity model; lifecycle/versioning/retraining as patterns evolve across geographies | **MLflow**; **Agent Bricks** for the GenAI re-engagement/personalization angle |
| **Genie Room (ask)** | Natural-language questions over churn/retention data | **Databricks SQL** (Genie over the SQL layer) |
| **Databricks App (surface)** | Retention cockpit for CRO/CFO + domain owners | Databricks App on top of the above |

> Note: Unity Catalog and Genie Room are FE Bar-mandated even though the use-case
> product list phrases them as Databricks SQL / governance — the build must
> include all six mandated stages.

## How each stage serves this problem
- **Lakeflow (ingest):** land raw synthetic developer-activity events (coding
  hours, AI-acceptance, session frequency), subscription lifecycle, and CRM
  campaign events into bronze tables.
- **Unity Catalog (govern):** register bronze/silver/gold + feature and model
  assets with ownership, lineage, and access control.
- **Lakebase (serve):** serve the current per-user churn score + state
  operationally so the CRM campaign trigger can read it low-latency.
- **ML / Gen AI (intelligence):** train and version (MLflow) a **daily churn
  propensity model** for Pro subscribers; use GenAI (Agent Bricks) to generate
  the **personalized re-engagement** message per at-risk user.
- **Genie (ask):** let CRO/CFO/analysts ask "what's this month's Pro churn?",
  "which geographies are trending worse?", "who are the at-risk power users?"
  in natural language.
- **Databricks App (surface):** a retention cockpit surfacing churn rate vs. the
  4% target, at-risk user lists, reactivation lift, and campaign outcomes for the
  CRO/CFO and the domain owners.
