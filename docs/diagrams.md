# Diagrams — for the pitch deck

Two slide-ready diagrams for the Retention Cockpit build. Both are authored in Mermaid
(left-to-right so they fit a 16:9 slide) with short labels kept large and legible.

**To put them on a slide:** paste a block into <https://mermaid.live>, export **SVG**
(crisp at any size) or PNG at ≥ 2× scale, and drop it onto the slide. Rendered copies
live alongside this file (`process-flow.svg`, `architecture.svg`). Keep labels short —
if a slide needs even less, cut the third line of a node, not the font size.

---

## 1. Process flow — how a user interacts with the app

The revenue team's journey through the cockpit, and the retention loop that closes when
outreach is logged. The dotted branch is the **future CRM integration** (not built).

```mermaid
flowchart LR
  U([Revenue leader /<br/>account manager]) --> APP{{Retention Cockpit<br/>Databricks App}}

  APP --> OV[Executive Overview<br/>churn vs 4% target · MRR at risk · ROI<br/>⚡ Genie 'so what' summary]
  APP --> WL[Retention Worklist<br/>priority queue, served from Lakebase]
  APP --> ASK[Ask tab<br/>Genie natural-language Q&A]

  WL --> DET[Open subscriber detail<br/>behavior + churn-risk drivers]
  DET --> DRAFT[Review AI-drafted<br/>re-engagement message]
  DRAFT --> LOG[/Log outreach/]
  LOG --> LOOP[Contacted subscriber<br/>drops off the queue live]
  LOOP --> WL

  LOG -. "future integration" .-> CRM[[CRM campaign send<br/>Salesforce · HubSpot]]
  CRM -. "outcome synced back" .-> LOOP

  classDef future stroke-dasharray:5 5,stroke:#888,color:#555;
  class CRM future;
```

**Read it as:** monitor (Overview) → act (Worklist → detail → AI draft → *Log outreach*)
→ the contacted user disappears from the queue immediately (the closed loop) → ask
(Genie). Today "Log outreach" writes to the governed log; **tomorrow** it hands off to
the CRM, which sends the campaign and syncs the outcome back.

---

## 2. Architecture — Databricks components

The six-stage journey wired end to end, plus the operational closed loop. Dotted edges
are future integrations.

```mermaid
flowchart LR
  RAW[(Synthetic dev-behavior data<br/>usage · subscriptions · CRM · support)]

  subgraph LH[Unity Catalog — governed lakehouse]
    direction LR
    BRZ[Lakeflow ingest<br/>→ bronze] --> SLV[silver] --> GLD[gold<br/>churn_serving · churn_predictions]
    GLD --> MV[Metric views<br/>churn_metrics_*]
  end

  subgraph INT[Intelligence]
    MODEL[MLflow churn model<br/>daily scoring]
    AGENT[Agent Bricks<br/>re-engagement drafts]
  end

  subgraph SRV[Lakebase — Postgres serving]
    SYNC[(synced replicas<br/>churn_serving · churn_predictions)]
    SOR[(system of record<br/>crm_outreach_log · app_narrative)]
  end

  GENIE[Genie Room<br/>NL Q&A]
  APP{{Retention Cockpit<br/>React + Fastify on Databricks Apps}}

  RAW --> BRZ
  MODEL --> GLD
  GLD -->|serverless reverse ETL| SYNC
  MV --> GENIE
  MV --> APP
  SYNC --> APP
  GENIE --> APP
  AGENT --> APP
  APP -->|Log outreach| SOR
  SOR -. "future PG→Delta sync" .-> SLV
  APP -. "future integration" .-> CRM[[CRM<br/>Salesforce · HubSpot]]

  classDef future stroke-dasharray:5 5,stroke:#888,color:#555;
  class CRM future;
```

**Stage mapping:** Lakeflow (ingest → bronze) · Unity Catalog (bronze→silver→gold +
metric views) · Lakebase (synced serving replicas + native system-of-record tables) ·
ML/Gen AI (MLflow daily scoring + Agent Bricks drafts) · Genie Room (NL Q&A over the
metric views) · Databricks App (the cockpit). Governed metric views are the single
semantic layer the app **and** Genie read, so their numbers can't diverge. The app
writes outreach to Lakebase (system of record); the dotted edges are the follow-ups
(PG→Delta outreach sync, and the CRM hand-off).
