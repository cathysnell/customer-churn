# Stage 4 — Intelligence (ML churn scoring)

Trains a per-user churn classifier on the governed feature/label table, scores the
current cohort, and writes the predictions back as a **governed gold table** that
syncs to Lakebase for the CRM trigger and the app (Stage 6).
Architecture: [`../docs/architecture.md`](../docs/architecture.md).

```
dev_churn.silver.churn_labels ──train──► UC model registry            ──score──► dev_churn.gold.churn_predictions ──reverse ETL──► Lakebase
  571k user-months, label=churned        dev_churn.gold.churn_model              one row/user: churn_score,           public.churn_predictions
                                          @champion alias                        risk band, model version, PK user_id
```

## Components

| Artifact | What / how |
| --- | --- |
| [`train_churn_model.py`](train_churn_model.py) | Serverless notebook. Trains a scikit-learn `HistGradientBoostingClassifier` on `dev_churn.silver.churn_labels` with a **temporal split** (hold out the latest month), MLflow-autologs, and registers the pipeline to UC `dev_churn.gold.churn_model` promoted to `@champion`. |
| [`score_churn.py`](score_churn.py) | Serverless notebook. Loads `@champion`, scores the latest at-risk month per user, and writes governed `dev_churn.gold.churn_predictions` (table + column comments, PK `user_id`, `model_version` audit column). |
| [`churn_ml_job.json`](churn_ml_job.json) | Serverless job `dev-churn-ml-scoring`: `train → score → sync_predictions`. The sync task reuses [`../serving/reverse_etl.py`](../serving/reverse_etl.py) with job parameters pointing at `churn_predictions`. Daily, paused by default. |

## Model

- **Algorithm:** `HistGradientBoostingClassifier` (scikit-learn) — no native deps beyond
  sklearn, trains on ~570k rows in seconds on serverless, and the whole preprocessing +
  model is one `Pipeline` so scoring is a single `predict_proba`.
- **Label:** `churned` (user was an active subscriber at month start and canceled during it).
- **Features:** monthly engagement signals — tenure, active days, avg coding hours,
  AI-acceptance rate, session frequency, the 30-day coding-hours trend (headline decline
  signal), support tickets, features adopted, CRM touches, and the power-user flag.
- **Leakage guards:** `churn_date` (NULL unless churned), `user_id`, and `month_start` are
  excluded from the feature set; the split is **temporal** (train on history, validate on
  the most recent month) rather than a random shuffle.
- **Class imbalance:** churn is rare (~4–5%/mo), so the positive class is up-weighted
  inversely to its frequency via per-sample weights.
- **Metrics:** ROC-AUC and **PR-AUC** (the honest headline for a rare-positive target),
  logged against the held-out month.

## Predictions table

`dev_churn.gold.churn_predictions` — one row per user:

| column | meaning |
| --- | --- |
| `user_id` (PK) | FK to `users.user_id`. |
| `as_of_month` | Observation month the features were drawn from. |
| `churn_score` | P(cancels next month), in [0,1]. |
| `churn_risk_band` | CRM trigger band: `high` (≥0.60), `medium` (≥0.30), `low`. |
| `model_name`, `model_version` | UC model that produced the score (audit trail). |
| `scored_at` | UTC write time. |

This table is **not** Lakeflow-owned, so `ALTER … COMMENT` / `PRIMARY KEY` apply cleanly
(unlike the silver streaming tables — see [Stage 2 evidence](../evidence/unity-catalog-governance.md)).

## Access / grants (per-stage model)

- Training and scoring run as the job's **run-as identity** — read on `dev_churn.silver`,
  write on `dev_churn.gold`, and register on the UC model. No human-group grant.
- The app reads the score from **Lakebase Postgres**, so its access is the same
  Postgres-side role grant to the app SP created in **Stage 6** — extended to
  `public.churn_predictions` alongside `public.churn_serving`.

## Deploy (requires approval — writes to the workspace)

```bash
# 1. Import the notebooks
databricks workspace import-dir ml/ /Workspace/Users/<you>/usage_events_ingest/ml --format AUTO --overwrite

# 2. Create the job (adjust notebook_path prefixes to your workspace)
databricks jobs create --json @ml/churn_ml_job.json

# 3. Run once and capture evidence
databricks jobs run-now --job-id <id>
```

## Evidence

See [`../evidence/ml-churn-run.md`](../evidence/ml-churn-run.md) (written after the first run):
holdout ROC-AUC / PR-AUC, the registered model version, the risk-band distribution, and
the row count synced to Lakebase.
