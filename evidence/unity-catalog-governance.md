# Unity Catalog governance — execution evidence (Stage 2)

Text evidence for the Stage 2 gate (governance: DDL + lineage + documentation).
Governance is **embedded in the Stage-1 pipeline** rather than applied as a separate
ALTER pass — the silver tables are Lakeflow-owned, so their comments/typing travel
in the pipeline definition. Captured 2026-09-10 on `fevm-serverless-stable-yuzk83`.

## Grants — per-stage model (not a monolithic Stage-2 grant)

Deliberately no human-group or blanket grant here. The consumers are service
principals introduced by later stages, each granted least-privilege when it exists:
Lakebase/serving reads run as their owner identity (Stage 3), and the app's
**Postgres-side** role grant lands in Stage 6 with the app SP. (UC also only resolves
account-level principals, which this workspace's operator cannot create — another
reason to grant per consumer rather than invent a group.)

## Registration intent (DDL) reconciled to reality

`sql/unity_catalog.sql` is generated from `src/datagen/schemas.py` and now targets
the **deployed** namespace `dev_churn.silver` (it previously named a never-deployed
`dev_behavior`/`bronze`+`gold`). A test asserts the committed file matches the
generator, so it cannot drift.

## Lineage (from `system.access.table_lineage`)

Every silver table traces to its bronze source — captured automatically by Lakeflow:

```
dev_churn.bronze.users_raw            -> dev_churn.silver.users
dev_churn.bronze.subscriptions_raw    -> dev_churn.silver.subscriptions
dev_churn.bronze.usage_events_raw     -> dev_churn.silver.usage_events
dev_churn.bronze.feature_adoption_raw -> dev_churn.silver.feature_adoption
dev_churn.bronze.support_tickets_raw  -> dev_churn.silver.support_tickets
dev_churn.bronze.crm_campaigns_raw    -> dev_churn.silver.crm_campaigns
dev_churn.bronze.crm_touches_raw      -> dev_churn.silver.crm_touches
dev_churn.bronze.churn_labels_raw     -> dev_churn.silver.churn_labels
```

## Documentation coverage (`information_schema.columns`)

Every silver table carries a table comment and a comment on **every** column
(100% coverage), set by the pipeline via an explicit schema DDL:

```
table               columns commented
users               13 / 13
subscriptions       19 / 19
usage_events         6 / 6
feature_adoption    10 / 10
support_tickets     13 / 13
crm_campaigns       10 / 10
crm_touches         13 / 13
churn_labels        15 / 15
```

Note on mechanism (verified the hard way): a Lakeflow streaming table does **not**
pick up UC column comments from DataFrame column metadata
(`alias(metadata={"comment": ...})` left them empty on DESCRIBE). Passing an explicit
`schema="col TYPE COMMENT '...'"` DDL to the table decorator is what sets them.

## Data-quality constraints

Governance also includes the pipeline's quality expectations (drop vs. warn),
proven in the Stage-1 evidence (`evidence/lakeflow-ingest-run.md`) — all pass except
`support_tickets.valid_csat`, since fixed to tolerate the NULL of an unanswered
survey (`csat_score IS NULL OR csat_score BETWEEN 1 AND 5`).
