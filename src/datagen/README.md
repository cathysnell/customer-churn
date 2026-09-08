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

# Small fast run — this is what the committed evidence comes from (~7s).
python -m datagen --sample-frac 0.004 --months 18 \
    --out data/sample --format parquet --no-partitions \
    --verify-reproducible \
    --evidence evidence/datagen-sample-run.md

# Full scale: 50,000 Pro users x 18 months of daily history.
python -m datagen --out data/full --format parquet

# Just print the schema; generate nothing.
python -m datagen --dictionary-only
```

`src/` is not installed by default, so either `pip install -e .` or prefix with
`PYTHONPATH=src`.

### Full vs sample

| | Sample | Full scale |
| --- | --- | --- |
| Command | `--sample-frac 0.004 --no-partitions` | *(defaults)* |
| Users | 200 | 50,000 |
| Months | 18 (unchanged) | 18 |
| `usage_events` rows | 43,514 | 10,778,146 |
| Total rows | 61,137 | 15,258,791 |
| On disk (snappy parquet) | ~820 KB | ~350 MB |
| Runtime (8-core laptop) | ~7 s | ~1 min generate, ~2 min with write |

Both row-count columns are measured, not estimated, and both runs are committed as
evidence: the sample in [`evidence/datagen-sample-run.md`](../../evidence/datagen-sample-run.md)
and the full run in [`evidence/datagen-fullscale-run.md`](../../evidence/datagen-fullscale-run.md).
At full scale: monthly churn **26,876 / 571,848 = 4.6999%**, reactivation
**3,444 / 43,090 = 7.9926%**, power-user share **11,146 / 50,000 = 22.29%**, all 23
consistency checks passing.

**No data is committed.** `data/` is gitignored in its entirety — no Parquet or CSV
artifact is tracked, at any size. The dataset is *reproducible from code*: the
generator is deterministic from committed seed `1729`, so any consumer materialises
it on demand rather than pulling bytes out of git.

Downstream stages read from a local generator run or from a **Databricks Volume**
the generator wrote to. What travels with the repo is the **text** proof that the
generator ran — row counts, `head()` previews, per-table digests and a two-run
reproducibility comparison under [`evidence/`](../../evidence). The one generated
artifact that *is* committed is [`sql/unity_catalog.sql`](../../sql/unity_catalog.sql),
because it is text, derives purely from the table specs, and the Unity Catalog stage
runs it verbatim (a test asserts it never drifts from the code).

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
| `--emit-ddl PATH` | — | Write the Unity Catalog DDL and exit. Needs no data. |
| `--verify-reproducible` | off | Regenerate into a temp dir, compare content **and** Parquet-byte digests, record in evidence §9c. |
| `--no-write` | off | Generate and validate in memory only. |
| `--dictionary-only` | off | Print the data dictionary and exit. |
| `--chunk-users` | `2500` | Users per chunk when generating daily rows. |
| `--quiet` | off | Suppress the stderr progress log. |

---

## Reproducibility

Seed **1729** is committed as `datagen.config.DEFAULT_SEED`. Two distinct claims,
each proved by a different check — worth keeping straight:

**1. Deterministic logical content (the guaranteed invariant).** For a fixed seed
and config, every table's column names, column order, row order and cell values
are identical on every run, on any machine. This is what
`writer.checksum_frames` hashes — a *canonical text rendering* of each frame
(header row + `to_csv(index=False)`), **not** the Parquet bytes — and what
`test_same_seed_produces_identical_content_checksums` asserts. The digests appear
in section 9a of the evidence.

**2. Byte-identical Parquet files (holds, but scoped to a pinned environment).**
`test_same_seed_produces_identical_parquet_bytes` writes two full runs to disk and
compares SHA-256 of the actual `.parquet` files; they match, for both the flat and
Hive-partitioned layouts. Section 9b of the evidence lists per-file digests and 9c
commits the two-run comparison. The scope matters: Parquet byte-equality is a
property of the *writer*, not of this generator — the file footer embeds the
pyarrow version string, so a pyarrow upgrade changes the bytes while leaving the
data identical. Claim 1 is the one that always holds.

Run `python -m datagen ... --verify-reproducible` to regenerate into a temp
directory, compare both digest sets, and record the outcome in the evidence
(non-zero exit on mismatch).

Note what is *not* reproducible: wall-clock stage timings and log timestamps.
Those are quarantined in a labelled appendix (section 12) precisely so the rest of
the report can be diffed byte-for-byte between two runs of the documented command.

Three design choices make the determinism hold:

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

A run writes into whatever `--out` points at (gitignored):

```
data/sample/                # local only — never committed
  users/part-00000.parquet
  usage_events/part-00000.parquet
  ...
  _manifest.json          # row counts, byte sizes, seed, full config, file list
  _unity_catalog.sql      # same DDL as the committed sql/unity_catalog.sql
```

With partitioning on (the default), tables declaring `partition_by` are written
Hive-style — `usage_events/event_date=2026-03-01/part-00000.parquet` — with the
partition column encoded in the path and dropped from the file body, as Delta
expects. `_manifest.json` and `_unity_catalog.sql` are the handoff contract to
the Lakeflow and Unity Catalog stages respectively — read from the local run
output (or a Databricks Volume the run wrote to), since none of it is committed.
`_unity_catalog.sql` is byte-identical to the committed
[`sql/unity_catalog.sql`](../../sql/unity_catalog.sql), so the governance stage can
work straight from the repo without generating anything.

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

Precisely: a **week** qualifies when the user hit ≥ 4 coding hours on ≥ 5 days; a
**month** qualifies when it contains a qualifying week; the **flag** is TRUE when
qualifying months are ≥ 50% of the months the user was active, over ≥ 2 active
months (`POWER_USER_MONTH_SHARE` / `POWER_USER_MIN_MONTHS` in `usage.py`). The same
wording appears in the `users.power_user_flag` column description and in the
evidence KPI label, so the stricter rule is never mistaken for the loose one.

The flag is measured from the **emitted** `usage_events` rows, not from latent
state, so any consumer can recompute it and agree.
`test_power_user_flag_is_recomputable_from_usage_events` recomputes the full
sustained rule and asserts **set equality** — not merely that flagged users
qualified at least once, which would pass under the loose rule too — and
`test_power_user_flag_is_stricter_than_ever_qualified` pins the distinction.

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

Reactivations are capped at **`MAX_REACTIVATIONS = 1`** per user, enforced in both
winback *eligibility* and *conversion*. The cap is what keeps three things
consistent: lifecycle state (one reactivation date, one post-winback churn date),
A03 billing (one reactivation term), and CRM outcomes (one `reactivated` touch).
`validate()` asserts `reactivated touches == reactivation terms` and prints both
counts into the evidence, and the test suite compares **per-user cardinality**, so
a regression cannot hide behind matching user-id sets.

---

## Tests

```bash
python -m pytest          # 155 tests, ~22s
python -m ruff check src tests
```

Coverage maps to the acceptance criteria:

| File | Asserts |
| --- | --- |
| `test_determinism.py` | same seed ⇒ identical frames, canonical-content digests **and emitted Parquet bytes** (flat + partitioned); different seed ⇒ different data; no wall-clock dependency; sub-stream stability |
| `test_schema.py` | exact columns in order, dtypes, non-nullability, unique PKs, every column documented, `conform` rejects drift |
| `test_referential_integrity.py` | no orphan `user_id`/`campaign_id`; no activity before signup or during a lapse; **support tickets inside an A03 term**; **reactivation touch/term cardinality + the MAX_REACTIVATIONS cap**; non-overlapping terms; acceptance rate matches its components |
| `test_churn_signal.py` | churners have lower late-window coding hours / acceptance / session frequency; negative correlations; churn rate in band and tunable; geo variation; **power-user flag recomputed exactly from `usage_events`**; retention touches *causally* reduce churn |
| `test_cli_and_output.py` | volume knobs; parquet round-trip; Hive layout; manifest; UC DDL; evidence sections **incl. churn numerator/denominator and timing segregation**; CLI flags |

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

All committed as text — the evaluator reads text only, not images. **This is the
only committed record of a run**: since no data files are tracked, these reports
carry the row counts, previews and digests that would otherwise require the
Parquet. Everything in them is regenerable by re-running the documented command.

| Artifact | What it proves |
| --- | --- |
| [`evidence/datagen-sample-run.md`](../../evidence/datagen-sample-run.md) | A 200-user sample run: exact command, config, row counts, KPIs **each with its numerator/denominator**, full data dictionary, `head()` previews + dtypes for all 8 tables, distributions, per-geo and per-month breakdowns, churn-signal correlations, 23 consistency checks, canonical-content digests (9a), per-file Parquet digests (9b), and the **two-run reproducibility comparison** (9c). |
| [`evidence/datagen-fullscale-run.md`](../../evidence/datagen-fullscale-run.md) | The same report at the brief's full volume: 50,000 users, 15,258,791 rows, churn 26,876/571,848 = 4.6999%, all checks passing. |
| [`evidence/datagen-fullscale-run.log`](../../evidence/datagen-fullscale-run.log) | Verbatim console log of that full-scale run. |
| [`evidence/pytest-output.txt`](../../evidence/pytest-output.txt) | Verbose test run + ruff output, with the pinned environment recorded. |
| [`sql/unity_catalog.sql`](../../sql/unity_catalog.sql) | The UC registration DDL as committed text; a test asserts it matches the generator exactly. |

Sections 1-11 of the two reports are reproducible from the seed; wall-clock timings
and log timestamps are quarantined in section 12 so the rest can be diffed
byte-for-byte.

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
