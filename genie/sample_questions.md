# Genie space — sample questions

Add these as the space's **sample/suggested questions** (the starter chips users see).
Each maps to a curated query in [`example_queries.sql`](example_queries.sql); together
they make a good demo script and a benchmark set for Genie's eval runs.

## Starter chips (put these on the space)

1. What is the latest monthly churn rate?
2. How has churn trended month over month?
3. How many users are in each churn risk band?
4. Who are the highest-risk Pro subscribers we should contact now?
5. How much monthly recurring revenue is at risk from high-risk subscribers?
6. Which regions have the highest churn?

## Deeper follow-ups (good live demo flow)

7. Do high-risk users show declining coding hours compared to low-risk users?
8. Which high-risk subscribers haven't received any CRM outreach in the last 30 days?
9. How does churn risk break down by persona and tier?
10. Are power users less likely to be high risk?
11. What's the average AI-suggestion acceptance rate for each risk band?
12. Show me high-risk users in EMEA sorted by MRR.

## Verified answers (2026-09-10, for the demo script)

Captured live so the presenter knows the expected shape:

- Latest monthly churn rate: **3.25%**.
- MRR at risk among currently-subscribed users: high band **1,849 users / ~$36.6K**,
  medium **2,921 / ~$58.7K**, low **21,798 / ~$446K**.
- Engagement by band — high risk: coding-hours trend **0.91** (declining), acceptance
  **0.247**; low risk: trend **1.02**, acceptance **0.463**. The decline signal holds.
- High-risk, currently-subscribed users with **zero** CRM touch in 30 days: **1,004** —
  the actionable gap the retention play closes.
