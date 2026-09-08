"""Orchestration: config in, a dict of validated DataFrames out.

:func:`generate` is the one function callers need. It runs the stages in
dependency order and then conforms every frame to its
:class:`~datagen.schemas.TableSpec` — a missing or extra column, or a dtype that
will not cast, fails the run here rather than in a downstream Databricks stage.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from datagen import schemas, tables
from datagen.config import GeneratorConfig
from datagen.lifecycle import Lifecycle, simulate
from datagen.population import Population, build_population
from datagen.usage import UsageResult, build_usage_events

LOGGER = logging.getLogger("datagen")


@dataclass
class GenerationResult:
    """Every emitted table plus the intermediate state and run diagnostics."""

    config: GeneratorConfig
    frames: dict[str, pd.DataFrame]
    population: Population
    lifecycle: Lifecycle
    usage: UsageResult
    timings: dict[str, float]

    @property
    def monthly_churn_rate(self) -> float:
        labels = self.frames["churn_labels"]
        if labels.empty:
            return 0.0
        return float(labels["churned"].mean())

    @property
    def row_counts(self) -> dict[str, int]:
        return {name: int(len(frame)) for name, frame in self.frames.items()}

    def reactivation_rate(self) -> float:
        """Share of delivered winback touches that reactivated the user."""
        touches = self.frames["crm_touches"]
        campaigns = self.frames["crm_campaigns"]
        if touches.empty or campaigns.empty:
            return 0.0
        winback_ids = set(campaigns.loc[campaigns["objective"] == "winback", "campaign_id"])
        delivered = touches[touches["campaign_id"].isin(winback_ids) & touches["delivered"]]
        if delivered.empty:
            return 0.0
        return float(delivered["reactivated"].mean())


def generate(config: GeneratorConfig) -> GenerationResult:
    """Run the full generator and return validated frames for every table."""
    timings: dict[str, float] = {}

    with _timed(timings, "population"):
        LOGGER.info(
            "building population: %s users, %s months (%s .. %s)",
            config.n_users,
            config.months,
            config.window_start.date(),
            config.window_end.date(),
        )
        population = build_population(config)

    with _timed(timings, "lifecycle"):
        LOGGER.info("simulating subscription lifecycle + CRM (calibrating churn hazard)")
        lifecycle = simulate(population)
        LOGGER.info(
            "hazard intercept calibrated to %.5f in %d iterations -> monthly churn %.4f "
            "(target %.4f)",
            lifecycle.intercept,
            lifecycle.calibration_iterations,
            lifecycle.realised_monthly_churn_rate,
            config.monthly_churn_rate,
        )

    with _timed(timings, "usage_events"):
        LOGGER.info("generating usage_events (active days only)")
        usage = build_usage_events(population, lifecycle)
        LOGGER.info("usage_events: %s rows", f"{usage.row_count:,}")

    frames: dict[str, pd.DataFrame] = {}

    with _timed(timings, "users"):
        frames["users"] = tables.build_users(population, usage)
    with _timed(timings, "subscriptions"):
        frames["subscriptions"] = tables.build_subscriptions(population, lifecycle)
    frames["usage_events"] = usage.events
    with _timed(timings, "feature_adoption"):
        frames["feature_adoption"] = tables.build_feature_adoption(population, lifecycle, usage)
    with _timed(timings, "support_tickets"):
        frames["support_tickets"] = tables.build_support_tickets(population, lifecycle)
    with _timed(timings, "crm_campaigns"):
        frames["crm_campaigns"] = tables.build_crm_campaigns(config)
    with _timed(timings, "crm_touches"):
        frames["crm_touches"] = tables.build_crm_touches(config, lifecycle)
    with _timed(timings, "churn_labels"):
        frames["churn_labels"] = tables.build_churn_labels(
            population, lifecycle, usage, frames["crm_touches"]
        )

    with _timed(timings, "conform"):
        frames = {name: conform(name, frame) for name, frame in frames.items()}

    for name in schemas.table_names():
        LOGGER.info("%-18s %10s rows", name, f"{len(frames[name]):,}")

    return GenerationResult(
        config=config,
        frames=frames,
        population=population,
        lifecycle=lifecycle,
        usage=usage,
        timings=timings,
    )


def conform(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Order columns and cast dtypes to match the table's spec, or raise.

    Nullable columns keep pandas' missing-value sentinels (``NaT`` for dates,
    ``NaN`` for floats, ``None`` for strings); non-nullable columns are asserted
    to be complete, which is what catches most generator bugs.
    """
    spec = schemas.spec(name)
    missing = [c for c in spec.column_names if c not in frame.columns]
    extra = [c for c in frame.columns if c not in spec.column_names]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")
    if extra:
        raise ValueError(f"{name}: unexpected columns {extra}")

    out = frame.loc[:, list(spec.column_names)].copy()
    for column in spec.columns:
        series = out[column.name]
        if column.dtype == "date":
            # Force nanosecond resolution: numpy datetime64[D]/[s] inputs would
            # otherwise leak through and make dtypes vary by source column.
            out[column.name] = (
                pd.to_datetime(series).astype("datetime64[ns]").dt.normalize()
            )
        elif column.dtype == "string":
            # Keep None distinguishable from the literal string "None".
            out[column.name] = series.astype(object).where(series.notna(), None)
        elif column.dtype == "bool":
            out[column.name] = series.fillna(False).astype(bool)
        elif column.dtype.startswith("int"):
            out[column.name] = series.astype(column.dtype)
        elif column.dtype == "float64":
            out[column.name] = pd.to_numeric(series, errors="raise").astype("float64")
        else:  # pragma: no cover - _SQL_TYPES keeps this exhaustive
            raise ValueError(f"{name}.{column.name}: unhandled dtype {column.dtype}")

        if not column.nullable and out[column.name].isna().any():
            n_null = int(out[column.name].isna().sum())
            raise ValueError(
                f"{name}.{column.name} is declared non-nullable but has {n_null} null(s)"
            )
    return out


def validate(result: GenerationResult) -> list[str]:
    """Cheap internal consistency checks. Returns a list of human-readable lines.

    Kept as returned strings rather than assertions so the CLI can print them
    into the evidence file as a passing/failing checklist.
    """
    frames = result.frames
    lines: list[str] = []

    users = set(frames["users"]["user_id"])
    child_tables = (
        "subscriptions",
        "usage_events",
        "feature_adoption",
        "support_tickets",
        "crm_touches",
        "churn_labels",
    )
    for child in child_tables:
        orphans = set(frames[child]["user_id"]) - users
        lines.append(
            f"referential integrity {child}.user_id -> users.user_id: "
            f"{'OK' if not orphans else f'FAIL ({len(orphans)} orphans)'}"
        )

    campaigns = set(frames["crm_campaigns"]["campaign_id"])
    orphan_campaigns = set(frames["crm_touches"]["campaign_id"]) - campaigns
    lines.append(
        "referential integrity crm_touches.campaign_id -> crm_campaigns.campaign_id: "
        f"{'OK' if not orphan_campaigns else f'FAIL ({len(orphan_campaigns)})'}"
    )

    for name in schemas.table_names():
        spec = schemas.spec(name)
        frame = frames[name]
        if not spec.primary_key or frame.empty:
            continue
        dupes = int(frame.duplicated(subset=list(spec.primary_key)).sum())
        lines.append(
            f"primary key {name}({', '.join(spec.primary_key)}): "
            f"{'OK' if dupes == 0 else f'FAIL ({dupes} duplicates)'}"
        )

    events = frames["usage_events"]
    if not events.empty:
        in_window = bool(
            (events["event_date"] >= result.config.window_start).all()
            and (events["event_date"] <= result.config.window_end).all()
        )
        lines.append(f"usage_events.event_date within window: {'OK' if in_window else 'FAIL'}")
        ranges_ok = bool(
            events["coding_hours"].between(0.0, 16.0).all()
            and events["ai_suggestion_acceptance_rate"].between(0.0, 1.0).all()
            and (events["session_frequency"] >= 1).all()
            and (events["suggestions_accepted"] <= events["suggestions_shown"]).all()
        )
        lines.append(f"usage_events value ranges plausible: {'OK' if ranges_ok else 'FAIL'}")

    rate = result.monthly_churn_rate
    target = result.config.monthly_churn_rate
    lines.append(
        f"monthly churn rate {rate:.4f} within +/-0.5pt of target {target:.4f}: "
        f"{'OK' if abs(rate - target) <= 0.005 else 'FAIL'}"
    )

    # No usage rows may exist after a cancellation with no reactivation.
    cancels = frames["subscriptions"]
    canceled = cancels.loc[cancels["cancel_date"].notna(), ["user_id", "cancel_date"]]
    if not canceled.empty and not events.empty:
        last_cancel = canceled.groupby("user_id", as_index=False)["cancel_date"].max()
        reactivated = set(
            cancels.loc[cancels["is_reactivation"], "user_id"]
        )
        check = events.merge(last_cancel, on="user_id", how="inner")
        check = check[~check["user_id"].isin(reactivated)]
        leaked = int((check["event_date"] > check["cancel_date"]).sum())
        lines.append(
            "no usage_events after cancellation (non-reactivated users): "
            f"{'OK' if leaked == 0 else f'FAIL ({leaked} rows)'}"
        )

    labels = frames["churn_labels"]
    if not labels.empty:
        churn_dates_ok = bool(labels.loc[labels["churned"], "churn_date"].notna().all())
        lines.append(
            "churn_labels.churn_date set whenever churned: "
            f"{'OK' if churn_dates_ok else 'FAIL'}"
        )

    return lines


class _timed:
    """Context manager recording wall-clock seconds into ``store[label]``."""

    def __init__(self, store: dict[str, float], label: str) -> None:
        self._store = store
        self._label = label

    def __enter__(self) -> _timed:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self._store[self._label] = round(time.perf_counter() - self._start, 3)


def churn_signal_summary(result: GenerationResult, late_window_months: int = 3) -> pd.DataFrame:
    """Compare late-window engagement between churned and retained users.

    This is the realism claim the brief makes, expressed as a table: users who
    churn should show materially lower coding hours, acceptance and session
    frequency in the months leading up to the churn than users who stay.

    Args:
        late_window_months: How many of the final months of each user's at-risk
            history count as the "late window".
    """
    labels = result.frames["churn_labels"]
    if labels.empty:
        return pd.DataFrame()

    ever_churned = labels.groupby("user_id")["churned"].max().rename("ever_churned")
    ranked = labels.sort_values(["user_id", "month_start"]).copy()
    ranked["from_end"] = ranked.groupby("user_id").cumcount(ascending=False)
    late = ranked[ranked["from_end"] < late_window_months]
    late = late.join(ever_churned, on="user_id")

    grouped = late.groupby("ever_churned").agg(
        users=("user_id", "nunique"),
        avg_coding_hours=("avg_coding_hours", "mean"),
        avg_acceptance_rate=("avg_acceptance_rate", "mean"),
        avg_session_frequency=("avg_session_frequency", "mean"),
        avg_active_days=("active_days", "mean"),
        avg_coding_hours_trend=("coding_hours_trend_30d", "mean"),
        avg_support_tickets=("support_tickets_30d", "mean"),
    )
    grouped.index = grouped.index.map({False: "retained", True: "churned"})
    grouped.index.name = "cohort"
    return grouped.round(4)


def geo_summary(result: GenerationResult) -> pd.DataFrame:
    """Per-geography user counts, churn rate and mean engagement."""
    labels = result.frames["churn_labels"]
    users = result.frames["users"]
    if labels.empty:
        return pd.DataFrame()

    per_geo = labels.groupby("geo").agg(
        at_risk_user_months=("churned", "size"),
        churn_events=("churned", "sum"),
        monthly_churn_rate=("churned", "mean"),
        avg_coding_hours=("avg_coding_hours", "mean"),
        avg_acceptance_rate=("avg_acceptance_rate", "mean"),
        avg_session_frequency=("avg_session_frequency", "mean"),
    )
    counts = users.groupby("geo").agg(
        users=("user_id", "nunique"), power_users=("power_user_flag", "sum")
    )
    out = counts.join(per_geo, how="left").fillna(0.0)
    out["power_user_share"] = (out["power_users"] / out["users"].replace(0, np.nan)).fillna(0.0)
    return out.round(4).sort_values("users", ascending=False)


def monthly_summary(result: GenerationResult) -> pd.DataFrame:
    """Churn rate and engagement by calendar month — the trend the deck shows."""
    labels = result.frames["churn_labels"]
    if labels.empty:
        return pd.DataFrame()
    out = labels.groupby("month_start").agg(
        at_risk_users=("churned", "size"),
        churn_events=("churned", "sum"),
        monthly_churn_rate=("churned", "mean"),
        avg_coding_hours=("avg_coding_hours", "mean"),
        avg_acceptance_rate=("avg_acceptance_rate", "mean"),
        avg_session_frequency=("avg_session_frequency", "mean"),
        power_user_months=("is_power_user_month", "sum"),
    )
    return out.round(4)
