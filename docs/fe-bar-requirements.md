# FE Bar Program — Requirements (summarized)

This is a faithful summary of the FE Bar submission requirements, organized so we can
check the build against it. Source of truth is the program brief; this doc is the
working checklist.

## The build brief

Build a **working prototype** that solves a customer problem in a **specific
industry**, as an **end-to-end data journey** starting from a **raw dataset** you
either generate synthetically or source from a publicly available dataset.

- **Effort:** plan for roughly **4–8 hours**, depending on whether you reuse an
  existing build or start from scratch.
- **Integrated, not siloed:** the journey must be wired across all stages below —
  each stage feeds the next, not six disconnected demos.

### Required stages (all six)

1. **Lakeflow** — ingest the raw data (synthetic or publicly available).
2. **Unity Catalog** — govern it.
3. **Lakebase** — operational serving.
4. **ML or Gen AI** — make it intelligent.
5. **Genie Room** — make it queryable in natural language.
6. **A Databricks app** — surface it to the business.

### Problem selection

- Pick a customer problem **specific to a real industry**.
  - Good: "A retail company with stockouts."
  - Not good: "Improve operations."
- Use the **Industry Outcome Maps** for guidance.
- Reusing something already built for a customer is allowed — but **confirm it
  contains all six elements above**.

## What to submit

### (1) The build — REQUIRED

- Code, notebooks, app, dashboards.
- **Crucially: include evidence the build actually ran, readable AS TEXT.**
  - Notebook cells committed **with their outputs visible**, logged run output,
    query results, or real model output committed in the repo.
  - The evaluator **reads text only** and **cannot see images** — a screenshot or
    screen recording does **NOT** count as execution evidence.
  - **Commit the output itself, not a picture of it.**
  - **Source code alone does not demonstrate execution and will not pass the Build
    domain.**
- **A GitHub repo link is REQUIRED, and the validator must be able to read it:**
  - Make it **public**, OR connect GitHub from the submission form if it lives in a
    private EMU org.
  - Submission is **blocked if the repo cannot be read** — so you find out before
    scoring, not after.
- **Data safety:** submit only your own solution artifacts — **never real customer
  data.** Scrub or synthesize any customer datasets, records, or customer-identifying
  content before pushing. Use synthetic or public data instead.

### (2) Presentation deck — REQUIRED

- The slides you'd present to the **business audience**.
- **Lead with the business outcome; quantify impact in the buyer's KPIs;** frame
  value for **both the executive sponsor and the domain owner.**
- Submit via the validator as one of:
  - a shareable **Google Slides** link (General access = "Anyone with the link",
    Viewer), or
  - a **PDF export**, or
  - an **HTML deck** (a Google Drive file link, or committed to the GitHub repo).
- If missing: Customer Skills is scored on the **narrative alone**, and the gap is
  flagged.

### (3) Conversation ID — OPTIONAL

- The session/conversation ID of the AI assistant used to create the build (Claude
  Code, Cursor, etc.).
- Can be added on the submission form; optional.
- If a build is flagged for possible cheating, it's requested then to verify how the
  build was produced. The submission form has a help link explaining how to find it
  per tool.

## Scoring domains referenced

- **Build** — needs real, text-readable execution evidence (not just source).
- **Customer Skills** — carried by the deck + narrative (outcome-led, KPI-quantified).
