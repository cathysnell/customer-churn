# ML churn scoring — execution evidence (Stage 4)

End-to-end run of the Stage-4 job on `fevm-serverless-stable-yuzk83`, captured
2026-09-10. Job `dev-churn-ml-scoring` (id `906316381173451`), run `187062642814343`
— **SUCCESS**. Serverless notebook tasks; deps via `%pip` in each notebook.

```
train (115s) ──► score (63s) ──► sync_predictions (56s)
  UC model registry   gold.churn_predictions   Lakebase public.churn_predictions
```

## Model — `dev_churn.gold.churn_model` v3 → `@champion`

HistGradientBoostingClassifier pipeline (median-impute numerics + passthrough bool),
trained on `dev_churn.silver.churn_labels` with a **temporal split** — the latest
month (`2026-08`) held out, trained on everything before it. MLflow run
`3baa8326e240418c9593b8d5c4705ba8`, registered to UC and promoted to `@champion`.

| Metric (held-out month) | Value |
| --- | --- |
| ROC-AUC | **0.955** |
| PR-AUC | **0.645** |
| Validation base rate (actual churn) | 0.0325 |

PR-AUC 0.645 against a 3.25% base rate is ~20× better than random — the model
strongly separates churners from the rest. (Autologged training-fit metrics for
reference: ROC-AUC 0.946, F1 0.904, precision 0.957, recall 0.874.)

## Predictions — `dev_churn.gold.churn_predictions`

Governed gold table written by the score task: one row per user for the latest
at-risk month.

| Check | Result |
| --- | --- |
| Rows / distinct users | 50000 / 50000 |
| `as_of_month` | 2026-08-01 |
| `model_version` | 3 |
| Column-comment coverage | 7 / 7 |
| Primary key (`user_id`) | present |
| `churn_score` range (min / avg / max) | 0.0022 / 0.458 / 0.9989 |

Risk-band distribution:

```
band     n       avg_score
high    20581    0.9029
medium   6066    0.4492
low     23353    0.0682
```

> **Calibration caveat.** The classifier is trained with inverse-frequency class
> weighting (the positive class is ~30× up-weighted), so `churn_score` is a strong
> *ranking* / relative propensity, **not** a calibrated probability — its absolute
> values sit far above the ~3–5% true base rate, and the fixed `0.30`/`0.60` bands
> therefore flag many more users than will actually churn. For a production trigger,
> either calibrate (e.g. `CalibratedClassifierCV`) or set the bands by score
> percentile / retention-team capacity rather than absolute thresholds. The score's
> *ordering* is what the CRM prioritization relies on and is sound (AUC 0.955).

## Served to Lakebase — `public.churn_predictions`

The `sync_predictions` task (the parameterized Stage-3 reverse-ETL notebook, pointed
at `churn_predictions`) full-snapshot loaded the gold table into Lakebase:

| Check | Result |
| --- | --- |
| Rows / distinct users | 50000 / 50000 |
| `model_version` / `as_of_month` | 3 / 2026-08-01 |
| Bands (low / high / medium) | 23353 / 20581 / 6066 (matches gold) |
| Per-user point lookup (laptop → endpoint) | ~53 ms |

## Bring-up fixes (runtime-only, caught by this run)

Two failures surfaced only on the live runtime — the model *trained* correctly in
every attempt; both were in the persistence/registry glue:

1. **skops serialization refused the sklearn pipeline.** Recent MLflow defaults to
   skops, which rejects `numpy.dtype` and the `ColumnTransformer` `remainder`
   (`passthrough`) list without a trusted-types allowlist. Fixed by pinning
   `serialization_format="cloudpickle"` in `mlflow.sklearn.log_model`.
2. **UC `search_model_versions` rejected the `run_id` filter** (`INVALID_PARAMETER_VALUE:
   … specify your filter … in the format name = 'model_name'`). Fixed by reading the
   version straight off the `log_model` result (`model_info.registered_model_version`)
   instead of searching.

Also observed: `sync_predictions` failed its **first** attempt with `The Python
kernel is unresponsive` — the same Arrow/grpc native-crash class seen in Stage 3 —
and **self-healed on the job's automatic retry**. Non-deterministic; no code change.
