# `datagen` — synthetic developer-behavior dataset generator

Stage 0 of the [FE Bar build](../../README.md): generates the raw dataset that the
Lakeflow → Unity Catalog → Lakebase → ML → Genie → App journey runs on.

> **Synthetic data only. Zero real customer data.** Every row is produced by this
> code from a committed random seed. Nothing derives from a real company, user, or
> telemetry stream. The Anysphere/Cursor archetype in
> [`docs/project-brief.md`](../../docs/project-brief.md) shapes the *schema and
> realism model*, never the values.

Pure Python + numpy/pandas/pyarrow. **No Databricks runtime needed** — it runs on
a laptop, and emits Unity Catalog registration DDL as text for the later stage.

---

## Quick start

```bash
pip install -r requirements.txt        # or: pip install -e ".[dev]"

# Small fast run — this is what the committed sample + evidence come from (~7s).
python -m datagen --sample-frac 0.004 --months 18 \
    --out data/sample --format parquet --no-partitions \
    --evidence evidence/datagen-sample-run.md

# Full scale: 50,000 Pro users x 18 months of daily history.
python -m datagen --out data/full --format parquet

# Just print the schema; generate nothing.
python -m datagen --dictionary-only
```

`src/` is not installed by default, so either `pip install -e .` or prefix with
`PYTHONPATH=src`.

### Full vs sample

| | Sample (committed) | Full scale |
| --- | --- | --- |
| Command | `--sample-frac 0.004 --no-partitions` | *(defaults)* |
| Users | 200 | 50,000 |
| Months | 18 (unchanged) | 18 |
| `usage_events` rows | 43,514 | 10,787,722 |
| Total rows | 61,148 | 15,288,022 |
| On disk (snappy parquet) | ~820 KB | ~350 MB |
| Runtime (8-core laptop) | ~7 s | ~1 min generate, ~2 min with write |

Both row-count columns are measured, not estimated: the sample numbers come from
the committed evidence file, and the full-scale numbers from an actual
`--users 50000 --months 18` run (realised churn 4.703%, power-user share 22.4%,
reactivation 7.98%, all consistency checks passing).

**Only the sample is committed** (`data/sample/`, ~820 KB). `.gitignore` blocks
bulk data; the full dataset is meant to be regenerated, never committed.

`--sample-frac` scales the **user count, not the time window** — all 18 months of
daily history are always generated. That is deliberate: the entire point of the
dataset is a *behavioural trend preceding churn*, and truncating the window would
destroy the signal the ML stage is supposed to learn. Sampling users keeps every
trend intact and every table proportionally populated.

### CLI flags

| Flag | Default | What it does |
| --- | --- | --- |
| `--users` | `50000` | Pro-tier users, before `--sample-frac`. |
| `--months` | `18` | Whole months of daily history. |
| `--sample-frac` | `1.0` | Scales `--users` for a fast run. Never truncates days. |
| `--seed` | `1729` | Master seed. **The committed reproducible value.** |
| `--end-date` | `2026-08-31` | Last day of the window. Never `today()`. |
| `--churn-rate` | `0.047` | Target monthly churn; the hazard is calibrated to it. |
| `--reactivation-rate` | `0.08` | Target CRM winback conversion rate. |
| `--campaigns` | `5` | CRM campaigns to run (4-6). |
| `--out` | `data/full` | Output directory. |
| `--format` | `parquet` | `parquet`, `csv` or `both`. |
| `--no-partitions` | off | One file per table instead of Hive dirs (for samples). |
| `--evidence PATH` | — | Write the markdown execution-evidence report. |
| `--no-write` | off | Generate and validate in memory only. |
| `--dictionary-only` | off | Print the data dictionary and exit. |
| `--chunk-users` | `2500` | Users per chunk when generating daily rows. |
| `--quiet` | off | Suppress the stderr progress log. |

---

## Reproducibility

Seed **1729** is committed as `datagen.config.DEFAULT_SEED`. Same seed ⇒
byte-identical output, asserted by `tests/test_determinism.py` and recorded as
per-table SHA-256 digests in the evidence file.

Three design choices make that hold:

1. **No wall-clock time.** The window is anchored to a fixed `end_date`
   (`2026-08-31`), never `date.today()`. A run today and a run next year agree.
2. **Named RNG sub-streams.** Every draw comes from
   `substream(seed, "users.geo")` etc., hashed with BLAKE2b — *not* `hash()`,
   whose string hashing is salted per process and would silently break
   reproducibility. Naming the streams also means adding a draw to one table
   cannot shift another table's numbers, so regenerating stays reviewable.
3. **Pre-generated draws in the lifecycle sim.** Churn calibration re-runs the
   simulation ~34 times while bisecting; drawing inside that loop would make each
   candidate see different randomness and the realised rate non-monotone.

---

## Output layout

```
data/sample/
  users/part-00000.parquet
  usage_events/part-00000.parquet
  ...
  _manifest.json          # row counts, byte sizes, seed, full config, file list
  _unity_catalog.sql      # CREATE TABLE DDL + PK/FK constraints for the UC stage
```

With partitioning on (the default), tables declaring `partition_by` are written
Hive-style — `usage_events/event_date=2026-03-01/part-00000.parquet` — with the
partition column encoded in the path and dropped from the file body, as Delta
expects. `_manifest.json` and `_unity_catalog.sql` are the handoff contract to
the Lakeflow and Unity Catalog stages respectively.

---

## Schema

Eight tables. `src/datagen/schemas.py` is the single source of truth: the
generator refuses to emit a frame that does not match it
(`datagen.pipeline.conform`), and the data dictionary, the evidence report and
the Unity Catalog DDL are all rendered from it. Full column-level docs:
`python -m datagen --dictionary-only`, or section 4 of
[`evidence/datagen-sample-run.md`](../../evidence/datagen-sample-run.md).

| Table | Asset | Grain | Notes |
| --- | --- | --- | --- |
| `users` | VA identity | user | geo, persona, plan, `power_user_flag` |
| `subscriptions` | **A03** billing | subscription term | signup, renewals, downgrades, cancel, revenue |
| `usage_events` | **A06** telemetry | user × **active** day | coding hours, AI-acceptance, session frequency |
| `feature_adoption` | **A07** adoption | user × feature × month | stickiness-feature activation |
| `support_tickets` | **A14** support | ticket | volume, chat messages, CSAT |
| `crm_campaigns` | VA campaign | campaign | objective, channel, segment, budget |
| `crm_touches` | VA touch | touch | channel, outcome, reactivation |
| `churn_labels` | derived (**gold**) | user × at-risk month | **the supervised target** |

Two grain decisions worth knowing:

- **`usage_events` emits only active days.** A user with a 52% active-day rate
  produces roughly half as many rows as there are days. This is why the realised
  row count (~10.9M at full scale) sits below the brief's ~27M full-density
  figure, and why density is reported in the evidence.
- **`churn_labels` has one row per user-month *at risk*** — i.e. months where the
  user was a subscriber on the first day. So `AVG(churned)` over the table *is*
  the monthly churn rate, with no denominator gymnastics downstream.

---

## The realism model

### Latent engagement drives everything

Each user gets a hidden monthly **engagement index** starting near 1.0:

```
index[i, m] = exp(drift[i] · m + shock[i, m] + season[m])
```

`drift` is the user's monthly log-drift, drawn from one of four behavioural
archetypes (`power`, `steady`, `casual`, `fading`). Coding hours, AI-acceptance,
session frequency and active-day probability are all derived from this one index,
which is what makes them **move together** — a user sliding out of the product
shows all three declining at once, exactly as the brief requires.

> The archetype is **deliberately not published** in `users`. Emitting it would
> leak the label into the feature set and make the downstream ML stage trivial.

Daily rows are then drawn around the monthly level (lognormal for hours, binomial
for suggestion acceptance, Poisson for counts), with weekend effects and calendar
seasonality (summer and December dips).

### Churn hazard

For every user-month at risk, a discrete-time logistic hazard:

```
logit(p) = intercept + Σ βₖ · xₖ
```

Sign conventions are the whole point of the dataset:

| Feature | β | Direction |
| --- | --- | --- |
| 1-month engagement decline | **+1.55** | declining ⇒ **more** churn |
| 3-month engagement decline | **+1.15** | a sustained slide, not one bad month |
| coding-hours level | −0.55 | heavy users stay |
| AI-acceptance rate | −0.32 | when it works for them, they stay |
| session frequency | −0.26 | habitual users stay |
| support tickets | +0.22 | friction (A14) pushes churn up |
| feature adoption (stickiness-weighted) | −0.85 | adoption is a moat (A07) |
| tenure | −0.34 | survivors keep surviving |
| annual plan | −0.85 | billing lock-in |
| geography | ±, per region | see below |
| retention touch received | −0.55 | **the program effect** |
| payment failure | +0.70 | involuntary churn |

**The intercept is not hand-tuned.** It is bisected (34 steps) until realised
monthly churn matches `--churn-rate`, default **4.7%** — the brief's illustrative
baseline. So the churn rate is a real knob, verified by
`test_churn_rate_is_tunable`.

### Geographic variation

Six regions (NA, EMEA, APAC, LATAM, MEA, ANZ) with distinct population shares,
coding-hours multipliers, AI-acceptance offsets, session multipliers, support
multipliers and churn-hazard shifts. APAC codes most; MEA least and churns most.
The evidence file breaks every KPI down per geo.

### Power users

The brief's bar is "≥ 4 coding hours/day on ≥ 5 days/week". Applied as *ever, in
any week*, that flags ~37% of an 18-month population — one strong week years ago
would brand a now-dormant user a power user. So `power_user_flag` requires the bar
to hold in a **majority of the months the user was actually active**, which makes
it mean *sustained* power user and lands the segment near 20-30%.

The flag is measured from the **emitted** `usage_events` rows, not from latent
state, so any consumer can recompute it from the data and agree
(`test_power_user_flag_is_recomputable_from_usage_events`).

### CRM motion

Five campaigns: two retention (at-risk actives), one winback (lapsed), one
adoption, one expansion. Two ordering rules keep the simulation causally honest:

- A retention touch is decided at the **start** of a month from state known at
  that point, then lowers that month's hazard — never assigned from an outcome
  that hasn't happened yet.
- `outcome = 'reactivated'` means exactly one thing: a **lapsed** user
  resubscribed via a **winback** touch. Retention touches act on already-active
  users and show up as hazard reduction, not as reactivations.

A won-back user gets a fresh subscription term, carries an elevated hazard
(winbacks are fragile), and may churn again — recorded as a distinct term with
status `churned_after_reactivation`.

---

## Tests

```bash
python -m pytest          # 144 tests, ~12s
python -m ruff check src tests
```

Coverage maps to the acceptance criteria:

| File | Asserts |
| --- | --- |
| `test_determinism.py` | same seed ⇒ identical frames & checksums; different seed ⇒ different data; no wall-clock dependency; sub-stream stability |
| `test_schema.py` | exact columns in order, dtypes, non-nullability, unique PKs, every column documented, `conform` rejects drift |
| `test_referential_integrity.py` | no orphan `user_id`/`campaign_id`; no activity before signup or during a lapse; non-overlapping terms; acceptance rate matches its components |
| `test_churn_signal.py` | churners have lower late-window coding hours / acceptance / session frequency; negative correlations; churn rate in band and tunable; geo variation; retention touches *causally* reduce churn |
| `test_cli_and_output.py` | volume knobs; parquet round-trip; Hive layout; manifest; UC DDL; evidence sections; CLI flags |

Two notes on how the behavioural tests are written:

- The **churn-rate band** is asserted both against the configured target (±0.5pt)
  and against a target-independent plausibility band (1-12%), so a mis-set
  default cannot pass by moving the goalposts.
- The **retention-touch effect** is verified as a counterfactual re-run at a
  *fixed* intercept, not by comparing touched vs untouched users. Observationally,
  touched users churn *more* — because touches deliberately target declining
  users — and end-to-end regeneration would hide the effect entirely, since
  calibration re-absorbs it into the intercept. See the docstring in
  `test_retention_touches_causally_reduce_churn`.

---

## Execution evidence

[`evidence/datagen-sample-run.md`](../../evidence/datagen-sample-run.md) — committed
text (the evaluator reads text only, not images). Contains the exact command, run
configuration, row counts, realised KPIs vs targets, the full data dictionary,
`head()` previews and dtypes for all 8 tables, distributions and per-geo /
per-month breakdowns, the churn-signal correlation check, consistency-check
results, per-table SHA-256 digests, the output manifest, and the verbatim console
log. [`evidence/pytest-output.txt`](../../evidence/pytest-output.txt) has the
passing test run.

---

## Module map

| Module | Responsibility |
| --- | --- |
| `config.py` | `GeneratorConfig`: volume/realism knobs, window arithmetic, committed seed |
| `rng.py` | named deterministic sub-streams |
| `reference.py` | geographies, archetypes, plans, features, campaigns |
| `schemas.py` | `TableSpec`s — the single source of truth for schema + DDL |
| `population.py` | users + latent monthly engagement trajectories |
| `lifecycle.py` | churn hazard, calibration, CRM touches, reactivation |
| `usage.py` | `usage_events` (chunked) + monthly aggregates + power-user flag |
| `tables.py` | the other seven table builders |
| `pipeline.py` | orchestration, schema conformance, validation, summaries |
| `writer.py` | parquet/csv output, manifest, Unity Catalog DDL, checksums |
| `evidence.py` | renders the markdown execution evidence |
| `cli.py` | argument parsing and the run log |
