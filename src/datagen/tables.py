"""Builders for every table except ``usage_events`` (see :mod:`datagen.usage`).

Each ``build_*`` function takes the already-simulated latent state and returns a
frame matching its :class:`~datagen.schemas.TableSpec`. None of them make
lifecycle decisions — churn, downgrades and reactivations were all decided in
:mod:`datagen.lifecycle`; these functions only render them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from datagen import reference as ref
from datagen.config import GeneratorConfig
from datagen.lifecycle import Lifecycle
from datagen.population import Population
from datagen.rng import choice_by_weight, substream
from datagen.usage import UsageResult

# CSAT falls when the ticket goes badly and when the user is already disengaging.
CSAT_RESPONSE_RATE = 0.58
PRIORITY_RESOLUTION_HOURS = {
    "P0_urgent": 3.5,
    "P1_high": 11.0,
    "P2_normal": 29.0,
    "P3_low": 54.0,
}
PRIORITY_FIRST_RESPONSE_MINUTES = {
    "P0_urgent": 14,
    "P1_high": 52,
    "P2_normal": 190,
    "P3_low": 480,
}


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


def build_users(population: Population, usage: UsageResult) -> pd.DataFrame:
    """The user dimension. ``power_user_flag`` is measured from emitted usage rows."""
    config = population.config
    signup = pd.to_datetime(population.signup_date)
    tenure = (config.window_end - signup).days.to_numpy()

    return pd.DataFrame(
        {
            "user_id": population.user_id,
            "signup_date": signup,
            "geo": population.geo,
            "country": population.country,
            "plan": population.plan_id,
            "tier": np.full(population.n_users, "pro", dtype=object),
            "persona": population.persona,
            "company_size": population.company_size,
            "acquisition_channel": population.acquisition_channel,
            "primary_language": population.primary_language,
            "ide_theme": population.ide_theme,
            "power_user_flag": usage.power_user_flag,
            "tenure_days_at_window_end": np.maximum(tenure, 0).astype(np.int64),
        }
    )


# ---------------------------------------------------------------------------
# subscriptions (A03)
# ---------------------------------------------------------------------------


def build_subscriptions(population: Population, lifecycle: Lifecycle) -> pd.DataFrame:
    """Subscription terms: one row per plan a user held for a contiguous period.

    A user has one term normally, two if they downgraded or were won back, three
    if both. Terms are emitted in chronological order per user, and revenue is
    recognised over the billed months inside the observation window.
    """
    config = population.config
    n = population.n_users
    # Nanosecond resolution keeps Timestamp arithmetic below free of numpy's
    # generic-unit deprecation warning.
    days = config.days.as_unit("ns")

    # Term boundaries as day offsets into the window. `term_start_date` keeps the
    # user's true signup date even when that predates the window; `_term` clamps
    # the *billing* span to the window separately (see `billed_from`).
    churn_day = lifecycle.churn_day_index
    churn2_day = lifecycle.churn2_day_index
    react_day = lifecycle.reactivation_day_index
    down_day = lifecycle.downgrade_day_index

    records: list[dict[str, object]] = []
    for i in range(n):
        user_id = population.user_id[i]
        plan_id = population.plan_id[i]
        signup_ts = pd.Timestamp(population.signup_date[i])
        term_index = 0

        # -- term boundaries for the first life: signup -> (downgrade | churn | open)
        cursor_ts = signup_ts
        cursor_plan = plan_id

        has_downgrade = down_day[i] >= 0
        has_churn = churn_day[i] >= 0
        has_react = react_day[i] >= 0

        if has_downgrade:
            d_ts = days[int(down_day[i])]
            records.append(
                _term(
                    config,
                    user_id,
                    cursor_plan,
                    cursor_ts,
                    # The term closes the day before the plan change. The unit is
                    # explicit because a bare `Timedelta(days=1)` is generic-unit
                    # and numpy now deprecates that conversion.
                    d_ts - pd.Timedelta(1, unit="D"),
                    term_index,
                    status="downgraded",
                    is_downgrade=False,
                    is_reactivation=term_index > 0,
                    payment_failures=int(lifecycle.payment_failures[i, :].sum())
                    if not has_churn
                    else 0,
                )
            )
            term_index += 1
            cursor_plan = ref.DOWNGRADE_TARGET[cursor_plan]
            cursor_ts = d_ts

        if has_churn:
            c_ts = days[int(churn_day[i])]
            records.append(
                _term(
                    config,
                    user_id,
                    cursor_plan,
                    cursor_ts,
                    c_ts,
                    term_index,
                    status="canceled",
                    is_downgrade=has_downgrade,
                    is_reactivation=False,
                    cancel_ts=c_ts,
                    cancel_reason=lifecycle.cancel_reason[i],
                    payment_failures=int(lifecycle.payment_failures[i, :].sum()),
                )
            )
            term_index += 1

            if has_react:
                r_ts = days[int(react_day[i])]
                # A winback lands on the entry-level monthly plan. It may itself
                # end in a second cancellation later in the window.
                second_churn = churn2_day[i] >= 0
                c2_ts = days[int(churn2_day[i])] if second_churn else None
                records.append(
                    _term(
                        config,
                        user_id,
                        "pro_monthly",
                        r_ts,
                        c2_ts,
                        term_index,
                        status="churned_after_reactivation" if second_churn else "active",
                        is_downgrade=False,
                        is_reactivation=True,
                        cancel_ts=c2_ts,
                        cancel_reason=(
                            lifecycle.cancel_reason_2[i] if second_churn else None
                        ),
                    )
                )
                term_index += 1
        else:
            records.append(
                _term(
                    config,
                    user_id,
                    cursor_plan,
                    cursor_ts,
                    None,
                    term_index,
                    status="active",
                    is_downgrade=has_downgrade,
                    is_reactivation=False,
                    payment_failures=int(lifecycle.payment_failures[i, :].sum()),
                )
            )

    frame = pd.DataFrame.from_records(records)
    frame.insert(0, "subscription_id", [f"SUB-{i:09d}" for i in range(1, len(frame) + 1)])
    return frame


def _term(
    config: GeneratorConfig,
    user_id: str,
    plan_id: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp | None,
    term_index: int,
    *,
    status: str,
    is_downgrade: bool,
    is_reactivation: bool,
    cancel_ts: pd.Timestamp | None = None,
    cancel_reason: object = None,
    payment_failures: int = 0,
) -> dict[str, object]:
    """Render one subscription term, including billed renewals and revenue."""
    plan = ref.PLAN_BY_ID[plan_id]
    effective_end = end_ts if end_ts is not None else config.window_end
    # Only bill for the part of the term inside the observation window.
    billed_from = max(start_ts, config.window_start)
    billed_days = max(int((effective_end - billed_from).days) + 1, 0)

    renewals = (
        billed_days // 365 if plan.billing_period == "annual" else billed_days // 30
    )
    revenue = round(plan.mrr_usd * (billed_days / 30.0), 2)

    return {
        "user_id": user_id,
        "plan_id": plan.plan_id,
        "plan_name": plan.plan_name,
        "tier": plan.tier,
        "billing_period": plan.billing_period,
        "mrr_usd": plan.mrr_usd,
        "list_price_usd": plan.list_price_usd,
        "term_start_date": start_ts,
        "term_end_date": end_ts,
        "term_index": term_index,
        "status": status,
        "renewals_count": int(max(renewals, 0)),
        "payment_failures": int(payment_failures),
        "is_downgrade": bool(is_downgrade),
        "is_reactivation": bool(is_reactivation),
        "cancel_date": cancel_ts,
        "cancel_reason": cancel_reason,
        "revenue_usd": revenue,
    }


# ---------------------------------------------------------------------------
# feature_adoption (A07)
# ---------------------------------------------------------------------------


def build_feature_adoption(
    population: Population, lifecycle: Lifecycle, usage: UsageResult
) -> pd.DataFrame:
    """One row per user per feature per month the user was a subscriber.

    Activation counts scale with the *emitted* active days that month, so a
    disengaging user's feature usage decays alongside their coding hours.
    """
    config = population.config
    months = population.months

    month_starts = config.month_starts.values
    month_idx = np.arange(months)
    subscriber = lifecycle.subscriber_month  # (n, months)
    active_days = usage.monthly_active_days  # (n, months)

    rng = substream(config.seed, "feature_adoption.usage")
    frames: list[pd.DataFrame] = []

    for f_idx, feature in enumerate(ref.FEATURES):
        first = population.feature_first_month[:, f_idx]  # (n,), -1 = never
        adopted = (first[:, None] >= 0) & (first[:, None] <= month_idx[None, :])
        emit = subscriber
        r, m = np.nonzero(emit)
        if len(r) == 0:
            continue

        is_adopted = adopted[r, m]
        # Feature-active days can never exceed the user's active days that month.
        feature_days = np.where(
            is_adopted,
            rng.binomial(np.maximum(active_days[r, m], 0), 0.35 + 0.45 * feature.base_adoption),
            0,
        ).astype(np.int64)
        activations = np.where(
            is_adopted,
            rng.poisson(np.maximum(feature_days * feature.activations_per_active_day, 0.0)),
            0,
        ).astype(np.int64)
        depth = np.where(
            (active_days[r, m] > 0) & is_adopted,
            np.clip(feature_days / np.maximum(active_days[r, m], 1), 0.0, 1.0),
            0.0,
        )

        # Typed NaT: a bare np.datetime64("NaT") has generic units and would
        # force an implicit-unit conversion warning from numpy.
        nat = np.datetime64("NaT", "ns")
        first_ts = np.where(
            first[r] >= 0,
            month_starts[np.clip(first[r], 0, months - 1)].astype("datetime64[ns]"),
            nat,
        )
        frames.append(
            pd.DataFrame(
                {
                    "month_start": month_starts[m],
                    "user_id": population.user_id[r],
                    "feature_key": np.full(len(r), feature.feature_key, dtype=object),
                    "feature_name": np.full(len(r), feature.feature_name, dtype=object),
                    "feature_family": np.full(len(r), feature.feature_family, dtype=object),
                    "is_adopted": is_adopted,
                    "first_activation_date": np.where(is_adopted, first_ts, nat),
                    "activation_count": activations,
                    "active_days": feature_days,
                    "depth_score": np.round(depth, 4),
                }
            )
        )

    if not frames:
        return pd.DataFrame(columns=list(_FEATURE_ADOPTION_COLUMNS))
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["month_start", "user_id", "feature_key"], kind="stable").reset_index(
        drop=True
    )


_FEATURE_ADOPTION_COLUMNS = (
    "month_start",
    "user_id",
    "feature_key",
    "feature_name",
    "feature_family",
    "is_adopted",
    "first_activation_date",
    "activation_count",
    "active_days",
    "depth_score",
)


# ---------------------------------------------------------------------------
# support_tickets (A14)
# ---------------------------------------------------------------------------


def build_support_tickets(population: Population, lifecycle: Lifecycle) -> pd.DataFrame:
    """Explode the per-month ticket counts from the population into ticket rows."""
    config = population.config
    counts = np.where(lifecycle.subscriber_month, population.support_tickets, 0)

    r, m = np.nonzero(counts)
    if len(r) == 0:
        return pd.DataFrame(columns=list(_SUPPORT_COLUMNS))

    per_cell = counts[r, m]
    row_user = np.repeat(r, per_cell)
    row_month = np.repeat(m, per_cell)
    n_rows = len(row_user)

    rng = substream(config.seed, "support.tickets")
    month_len = _month_lengths(config)
    day_in_month = np.floor(rng.random(n_rows) * month_len[row_month]).astype(np.int64)
    created = config.month_starts.values[row_month].astype("datetime64[ns]") + day_in_month.astype(
        "timedelta64[D]"
    ).astype("timedelta64[ns]")

    channel = choice_by_weight(rng, n_rows, ref.SUPPORT_CHANNELS)
    category = choice_by_weight(rng, n_rows, ref.SUPPORT_CATEGORIES)
    priority = choice_by_weight(rng, n_rows, ref.SUPPORT_PRIORITIES)

    res_scale = np.array([PRIORITY_RESOLUTION_HOURS[p] for p in priority], dtype=float)
    resolution_hours = np.round(res_scale * rng.gamma(2.0, 0.5, size=n_rows), 2)
    fr_scale = np.array([PRIORITY_FIRST_RESPONSE_MINUTES[p] for p in priority], dtype=float)
    first_response = np.maximum(rng.poisson(fr_scale), 1).astype(np.int64)

    chat_messages = np.maximum(rng.poisson(4.6), 1).astype(np.int64) + rng.integers(
        0, 4, size=n_rows
    )
    reopened = rng.binomial(2, 0.09, size=n_rows).astype(np.int64)
    escalated = rng.random(n_rows) < np.where(
        np.isin(priority, ["P0_urgent", "P1_high"]), 0.34, 0.06
    )
    resolved = rng.random(n_rows) < 0.93

    # CSAT: worse for escalated/reopened tickets and for disengaging users.
    engagement = population.engagement_index[row_user, row_month]
    csat_mean = np.clip(
        4.25
        + 0.35 * np.clip(engagement - 1.0, -1.0, 0.5)
        - 0.55 * escalated
        - 0.40 * reopened
        - 0.90 * (~resolved),
        1.0,
        5.0,
    )
    csat_raw = np.clip(np.round(csat_mean + rng.normal(0.0, 0.75, size=n_rows)), 1.0, 5.0)
    responded = rng.random(n_rows) < CSAT_RESPONSE_RATE
    csat = np.where(responded, csat_raw, np.nan)

    frame = pd.DataFrame(
        {
            "user_id": population.user_id[row_user],
            "created_date": created,
            "channel": channel,
            "category": category,
            "priority": priority,
            "chat_message_count": chat_messages,
            "first_response_minutes": first_response,
            "resolution_hours": resolution_hours,
            "reopened_count": reopened,
            "is_escalated": escalated,
            "csat_score": csat,
            "resolved": resolved,
        }
    ).sort_values(["created_date", "user_id"], kind="stable").reset_index(drop=True)
    frame.insert(0, "ticket_id", [f"TCK-{i:09d}" for i in range(1, len(frame) + 1)])
    return frame


_SUPPORT_COLUMNS = (
    "ticket_id",
    "user_id",
    "created_date",
    "channel",
    "category",
    "priority",
    "chat_message_count",
    "first_response_minutes",
    "resolution_hours",
    "reopened_count",
    "is_escalated",
    "csat_score",
    "resolved",
)


def _month_lengths(config: GeneratorConfig) -> np.ndarray:
    starts = config.month_starts
    ends = starts + pd.offsets.MonthEnd(0)
    ends = ends.where(ends <= config.window_end, config.window_end)
    return ((ends - starts).days + 1).to_numpy()


# ---------------------------------------------------------------------------
# crm_campaigns / crm_touches
# ---------------------------------------------------------------------------


def build_crm_campaigns(config: GeneratorConfig) -> pd.DataFrame:
    """The campaign dimension, with run dates resolved from the window start.

    Dates are computed arithmetically rather than by indexing ``month_starts``,
    because a short ``--months`` window can end before a later campaign was
    scheduled to launch. Such a campaign is still emitted in the dimension (it
    is a real campaign definition) with a ``start_date`` past ``window_end``, and
    the lifecycle simulation simply never marks it live — so it correctly gets
    zero touches instead of silently borrowing another campaign's schedule.
    """
    rows = []
    for campaign in ref.CAMPAIGNS[: config.campaigns]:
        start = config.window_start + pd.DateOffset(months=campaign.month_offset)
        last_month = start + pd.DateOffset(months=campaign.duration_months - 1)
        end = min(last_month + pd.offsets.MonthEnd(0), config.window_end)
        # A campaign that never launched inside the window has no live days.
        end = max(end, start)
        rows.append(
            {
                "campaign_id": campaign.campaign_id,
                "campaign_name": campaign.campaign_name,
                "objective": campaign.objective,
                "channel": campaign.channel,
                "target_segment": campaign.target_segment,
                "offer_type": campaign.offer_type,
                "budget_usd": campaign.budget_usd,
                "start_date": start,
                "end_date": end,
                "is_active_at_window_end": bool(
                    start <= config.window_end <= end
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


def build_crm_touches(config: GeneratorConfig, lifecycle: Lifecycle) -> pd.DataFrame:
    """Render the touch log recorded during the lifecycle simulation."""
    touches = lifecycle.touches
    if touches.empty:
        return pd.DataFrame(columns=list(_TOUCH_OUT_COLUMNS))

    frame = touches.copy()
    frame["touch_date"] = config.days.values[frame["touch_day_index"].to_numpy()]
    frame = frame.drop(columns=["touch_day_index"])
    frame = frame.sort_values(["touch_date", "campaign_id", "user_id"], kind="stable").reset_index(
        drop=True
    )
    frame.insert(0, "touch_id", [f"TCH-{i:010d}" for i in range(1, len(frame) + 1)])
    return frame


_TOUCH_OUT_COLUMNS = (
    "touch_id",
    "campaign_id",
    "user_id",
    "touch_date",
    "channel",
    "message_variant",
    "delivered",
    "opened",
    "clicked",
    "outcome",
    "reactivated",
    "user_state_at_touch",
    "cost_usd",
)


# ---------------------------------------------------------------------------
# churn_labels
# ---------------------------------------------------------------------------


def build_churn_labels(
    population: Population,
    lifecycle: Lifecycle,
    usage: UsageResult,
    touches: pd.DataFrame,
) -> pd.DataFrame:
    """The supervised training target, one row per at-risk user-month.

    Rows exist only for months where the user was a subscriber on the first day,
    so ``AVG(churned)`` over this table *is* the monthly churn rate — no
    denominator gymnastics needed downstream.

    Behavioural columns are computed from the **emitted** ``usage_events`` rows
    (via :class:`~datagen.usage.UsageResult` aggregates) rather than from latent
    state, so a consumer joining this table to ``usage_events`` sees consistent
    numbers.
    """
    config = population.config
    months = population.months
    month_starts = config.month_starts.values

    at_risk = lifecycle.at_risk
    r, m = np.nonzero(at_risk)
    if len(r) == 0:
        return pd.DataFrame(columns=list(_CHURN_COLUMNS))

    avg_hours = usage.monthly_avg_coding_hours
    # Month-over-month coding-hours trend from emitted rows. Month 0 and months
    # with no prior activity are reported as 1.0 (flat) rather than a fake dip.
    prev = np.concatenate([avg_hours[:, :1], avg_hours[:, :-1]], axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        trend = np.where(prev > 0, avg_hours / prev, 1.0)
    trend = np.nan_to_num(trend, nan=1.0, posinf=1.0)

    tenure_months = np.maximum(
        np.arange(months)[None, :] - population.signup_month_index[:, None], 0
    )
    touch_counts = _touch_counts_per_user_month(config, population, touches)

    # Date each churn from the month it happened in, so a won-back user's second
    # cancellation is not dated to their first.
    churn_day = lifecycle.churn_day_by_month[r, m]
    churned = lifecycle.churned[r, m]
    churn_ts = np.where(
        churned,
        config.days.values[np.clip(churn_day, 0, config.n_days - 1)].astype("datetime64[ns]"),
        np.datetime64("NaT", "ns"),
    )

    return pd.DataFrame(
        {
            "month_start": month_starts[m],
            "user_id": population.user_id[r],
            "geo": population.geo[r],
            "churned": churned,
            "churn_date": churn_ts,
            "tenure_months": tenure_months[r, m].astype(np.int64),
            "is_power_user_month": usage.monthly_power_weeks[r, m] > 0,
            "active_days": usage.monthly_active_days[r, m].astype(np.int64),
            "avg_coding_hours": np.round(avg_hours[r, m], 3),
            "avg_acceptance_rate": np.round(usage.monthly_avg_acceptance[r, m], 4),
            "avg_session_frequency": np.round(usage.monthly_avg_sessions[r, m], 3),
            "coding_hours_trend_30d": np.round(np.clip(trend[r, m], 0.0, 5.0), 4),
            "support_tickets_30d": population.support_tickets[r, m].astype(np.int64),
            "features_adopted": population.features_adopted[r, m].astype(np.int64),
            "crm_touches_30d": touch_counts[r, m].astype(np.int64),
        }
    ).sort_values(["month_start", "user_id"], kind="stable").reset_index(drop=True)


_CHURN_COLUMNS = (
    "month_start",
    "user_id",
    "geo",
    "churned",
    "churn_date",
    "tenure_months",
    "is_power_user_month",
    "active_days",
    "avg_coding_hours",
    "avg_acceptance_rate",
    "avg_session_frequency",
    "coding_hours_trend_30d",
    "support_tickets_30d",
    "features_adopted",
    "crm_touches_30d",
)


def _touch_counts_per_user_month(
    config: GeneratorConfig, population: Population, touches: pd.DataFrame
) -> np.ndarray:
    """``(n_users, months)`` count of CRM touches, for the label table."""
    counts = np.zeros((population.n_users, population.months), dtype=np.int64)
    if touches.empty:
        return counts

    row_of_user = {uid: i for i, uid in enumerate(population.user_id)}
    rows = touches["user_id"].map(row_of_user).to_numpy()
    month_period = pd.DatetimeIndex(touches["touch_date"]).to_period("M")
    first = config.month_starts.to_period("M")[0]
    month_idx = np.array([(p - first).n for p in month_period], dtype=np.int64)

    valid = (month_idx >= 0) & (month_idx < population.months)
    flat = rows[valid] * population.months + month_idx[valid]
    binned = np.bincount(flat, minlength=counts.size)
    return binned.reshape(counts.shape).astype(np.int64)
