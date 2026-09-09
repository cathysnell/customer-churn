"""``usage_events`` (A06) — the daily behavioural signal.

One row per user per **active** day. Inactive days are not emitted, which is why
the realised row count sits well below ``users x days``; the brief calls this out
(~27M rows at full density for 50k users x 547 days).

Each day's values are drawn around the user's *monthly* latent level from
:mod:`datagen.population`, so a user whose engagement index is sliding produces
daily rows whose coding hours, acceptance rate and session frequency all slide
together. Users are processed in chunks of ``config.chunk_users`` so full-scale
runs never materialise an ``(n_users, n_days)`` float matrix.

This module also measures the published ``users.power_user_flag`` from the
emitted rows rather than from latent state, so the dataset is self-consistent:
anyone can recompute the flag from ``usage_events`` and get the same answer.
See :data:`POWER_USER_MONTH_SHARE` for why the bar is "sustained" rather than
"ever".
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from datagen.config import GeneratorConfig
from datagen.lifecycle import Lifecycle
from datagen.population import Population
from datagen.rng import substream
from datagen.schemas import USAGE_EVENTS

#: Day-to-day dispersion of coding hours around the monthly level (log scale).
DAILY_HOURS_LOG_SIGMA = 0.42

#: Day-to-day dispersion of the acceptance rate (additive, then clipped).
DAILY_ACCEPTANCE_SIGMA = 0.055

#: Weekends see less activity and shorter sessions.
WEEKEND_ACTIVE_MULT = 0.42
WEEKEND_HOURS_MULT = 0.68

#: Share of a user's *observed* months that must contain a qualifying power week
#: for ``users.power_user_flag`` to be TRUE.
#:
#: The brief defines the bar as ">= 4 coding hours/day on >= 5 days/week". Applied
#: as "ever, in any week", that flags ~37% of an 18-month population — one good
#: week years ago would brand a now-dormant user a power user, which is useless
#: as a segment and as a model feature. Requiring the bar to hold in a majority
#: of the months the user was actually active makes the flag mean "sustained
#: power user", and lands the segment near the intended ~18-20%.
POWER_USER_MONTH_SHARE = 0.5

#: A user needs at least this many observed months before the flag can be TRUE
#: (one strong month is not a sustained pattern).
POWER_USER_MIN_MONTHS = 2

#: AI suggestions shown scales with hours; requests and edits scale with both.
SUGGESTIONS_PER_HOUR = 34.0
AI_REQUESTS_PER_HOUR = 3.1
LOC_PER_HOUR = 62.0
FILES_PER_HOUR = 4.4


@dataclass
class UsageResult:
    """Emitted daily rows plus the monthly aggregates the other tables need.

    ``monthly_*`` matrices are ``(n_users, months)`` and aligned to
    :class:`~datagen.population.Population` row order. They exist so
    ``churn_labels`` and ``feature_adoption`` describe the *emitted* data rather
    than re-deriving from latent state (which could silently diverge).
    """

    events: pd.DataFrame
    monthly_active_days: np.ndarray
    monthly_coding_hours_sum: np.ndarray
    monthly_acceptance_sum: np.ndarray
    monthly_sessions_sum: np.ndarray
    monthly_power_weeks: np.ndarray
    power_user_flag: np.ndarray
    row_count: int = field(default=0)

    def monthly_mean(self, total: np.ndarray) -> np.ndarray:
        """Mean per active day, 0.0 where there were no active days."""
        with np.errstate(invalid="ignore", divide="ignore"):
            out = np.where(self.monthly_active_days > 0, total / self.monthly_active_days, 0.0)
        return np.nan_to_num(out)

    @property
    def monthly_avg_coding_hours(self) -> np.ndarray:
        return self.monthly_mean(self.monthly_coding_hours_sum)

    @property
    def monthly_avg_acceptance(self) -> np.ndarray:
        return self.monthly_mean(self.monthly_acceptance_sum)

    @property
    def monthly_avg_sessions(self) -> np.ndarray:
        return self.monthly_mean(self.monthly_sessions_sum)


def build_usage_events(population: Population, lifecycle: Lifecycle) -> UsageResult:
    """Generate ``usage_events`` and the monthly aggregates derived from it."""
    config = population.config
    n, months = population.n_users, population.months

    monthly_active_days = np.zeros((n, months), dtype=np.int64)
    monthly_hours = np.zeros((n, months), dtype=float)
    monthly_acceptance = np.zeros((n, months), dtype=float)
    monthly_sessions = np.zeros((n, months), dtype=float)
    monthly_power_weeks = np.zeros((n, months), dtype=np.int64)

    day_month = _day_to_month_index(config)
    day_week = _day_to_week_index(config)
    is_weekend = _is_weekend(config)

    frames: list[pd.DataFrame] = []
    for chunk in _chunks(n, config.chunk_users):
        result = _build_chunk(
            population, lifecycle, chunk, day_month, day_week, is_weekend
        )
        frames.append(result["events"])
        monthly_active_days[chunk] = result["active_days"]
        monthly_hours[chunk] = result["hours_sum"]
        monthly_acceptance[chunk] = result["acceptance_sum"]
        monthly_sessions[chunk] = result["sessions_sum"]
        monthly_power_weeks[chunk] = result["power_weeks"]

    power_flag = _power_user_flag(monthly_power_weeks, monthly_active_days)

    events = pd.concat(frames, ignore_index=True) if frames else _empty_events()
    events = events.sort_values(["event_date", "user_id"], kind="stable").reset_index(drop=True)

    return UsageResult(
        events=events,
        monthly_active_days=monthly_active_days,
        monthly_coding_hours_sum=monthly_hours,
        monthly_acceptance_sum=monthly_acceptance,
        monthly_sessions_sum=monthly_sessions,
        monthly_power_weeks=monthly_power_weeks,
        power_user_flag=power_flag,
        row_count=len(events),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _power_user_flag(
    monthly_power_weeks: np.ndarray, monthly_active_days: np.ndarray
) -> np.ndarray:
    """TRUE for users who *sustained* the power-user bar, not who ever touched it.

    A month counts as observed if the user was active at all in it; a month
    qualifies if it contained at least one week meeting the brief's bar. The flag
    requires qualifying months to be a majority of observed months, so a single
    strong week in an 18-month history does not brand a dormant user.
    """
    observed = (monthly_active_days > 0).sum(axis=1)
    qualifying = (monthly_power_weeks > 0).sum(axis=1)
    enough_history = observed >= POWER_USER_MIN_MONTHS
    sustained = qualifying >= np.ceil(POWER_USER_MONTH_SHARE * np.maximum(observed, 1))
    return enough_history & sustained & (qualifying > 0)


def _chunks(n: int, size: int) -> Iterator[np.ndarray]:
    for start in range(0, n, size):
        yield np.arange(start, min(start + size, n))


def _day_to_month_index(config: GeneratorConfig) -> np.ndarray:
    """For each day in the window, which month column it belongs to."""
    day_months = config.days.to_period("M")
    first = config.month_starts.to_period("M")[0]
    return (day_months - first).n.astype(np.int64) if hasattr(
        day_months - first, "n"
    ) else np.array([(p - first).n for p in day_months], dtype=np.int64)


def _day_to_week_index(config: GeneratorConfig) -> np.ndarray:
    """Sequential ISO-week index per day, so power-user weeks can be counted."""
    days = config.days
    # Monday-anchored week number relative to the first Monday on/before day 0.
    return ((days - days[0]).days + days[0].weekday()) // 7


def _is_weekend(config: GeneratorConfig) -> np.ndarray:
    return config.days.dayofweek.values >= 5


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype="object") for name in USAGE_EVENTS.column_names})


def _build_chunk(
    population: Population,
    lifecycle: Lifecycle,
    rows: np.ndarray,
    day_month: np.ndarray,
    day_week: np.ndarray,
    is_weekend: np.ndarray,
) -> dict[str, object]:
    """Generate every active-day row for one chunk of users."""
    config = population.config
    n_chunk = len(rows)
    n_days = config.n_days
    months = population.months
    chunk_id = int(rows[0])

    # Broadcast the monthly latent level down to per-day expectations.
    hours_level = population.month_coding_hours[rows][:, day_month]
    accept_level = population.month_acceptance[rows][:, day_month]
    sessions_level = population.month_sessions[rows][:, day_month]
    active_prob = population.month_active_day_prob[rows][:, day_month]

    weekend = is_weekend[None, :]
    active_prob = np.where(weekend, active_prob * WEEKEND_ACTIVE_MULT, active_prob)

    subscribed = lifecycle.subscribed_day[rows]

    rng_active = substream(config.seed, "usage.active", chunk_id)
    active = (rng_active.random((n_chunk, n_days)) < active_prob) & subscribed

    r, d = np.nonzero(active)
    if len(r) == 0:
        return {
            "events": _empty_events(),
            "active_days": np.zeros((n_chunk, months), dtype=np.int64),
            "hours_sum": np.zeros((n_chunk, months)),
            "acceptance_sum": np.zeros((n_chunk, months)),
            "sessions_sum": np.zeros((n_chunk, months)),
            "power_weeks": np.zeros((n_chunk, months), dtype=np.int64),
        }

    n_rows = len(r)
    rng = substream(config.seed, "usage.daily", chunk_id)

    weekend_row = is_weekend[d]
    mu = np.log(np.maximum(hours_level[r, d], 0.05))
    mu = mu + np.where(weekend_row, np.log(WEEKEND_HOURS_MULT), 0.0)
    coding_hours = np.clip(
        np.exp(mu + rng.normal(0.0, DAILY_HOURS_LOG_SIGMA, size=n_rows)), 0.05, 16.0
    )

    suggestions_shown = np.maximum(
        rng.poisson(np.maximum(coding_hours * SUGGESTIONS_PER_HOUR, 0.5)), 1
    ).astype(np.int64)
    p_accept = np.clip(
        accept_level[r, d] + rng.normal(0.0, DAILY_ACCEPTANCE_SIGMA, size=n_rows), 0.01, 0.98
    )
    suggestions_accepted = rng.binomial(suggestions_shown, p_accept).astype(np.int64)
    acceptance_rate = suggestions_accepted / suggestions_shown

    sessions = np.maximum(
        rng.poisson(np.maximum(sessions_level[r, d] * np.where(weekend_row, 0.6, 1.0), 0.2)), 1
    ).astype(np.int64)

    loc = rng.poisson(np.maximum(coding_hours * LOC_PER_HOUR, 1.0)).astype(np.int64)
    files = np.maximum(
        rng.poisson(np.maximum(coding_hours * FILES_PER_HOUR, 0.5)), 1
    ).astype(np.int64)
    ai_requests = rng.poisson(np.maximum(coding_hours * AI_REQUESTS_PER_HOUR, 0.2)).astype(
        np.int64
    )

    events = pd.DataFrame(
        {
            "event_date": config.days.values[d],
            "user_id": population.user_id[rows][r],
            "geo": population.geo[rows][r],
            "coding_hours": np.round(coding_hours, 3),
            "ai_suggestion_acceptance_rate": np.round(acceptance_rate, 4),
            "session_frequency": sessions,
            "suggestions_shown": suggestions_shown,
            "suggestions_accepted": suggestions_accepted,
            "lines_of_code_written": loc,
            "files_touched": files,
            "ai_requests": ai_requests,
            "is_weekend": weekend_row,
        }
    )

    aggregates = _aggregate(
        n_chunk, months, r, d, day_month, day_week, coding_hours, acceptance_rate, sessions, config
    )
    aggregates["events"] = events
    return aggregates


def _aggregate(
    n_chunk: int,
    months: int,
    r: np.ndarray,
    d: np.ndarray,
    day_month: np.ndarray,
    day_week: np.ndarray,
    coding_hours: np.ndarray,
    acceptance_rate: np.ndarray,
    sessions: np.ndarray,
    config: GeneratorConfig,
) -> dict[str, object]:
    """Roll emitted rows up to per-user-per-month aggregates and the power flag."""
    month_of_row = day_month[d]
    flat = r * months + month_of_row
    size = n_chunk * months

    active_days = np.bincount(flat, minlength=size).reshape(n_chunk, months).astype(np.int64)
    hours_sum = np.bincount(flat, weights=coding_hours, minlength=size).reshape(n_chunk, months)
    accept_sum = np.bincount(flat, weights=acceptance_rate, minlength=size).reshape(
        n_chunk, months
    )
    sessions_sum = np.bincount(flat, weights=sessions.astype(float), minlength=size).reshape(
        n_chunk, months
    )

    # Power-user bar: >= power_user_hours on >= power_user_days days in one week.
    qualifying = coding_hours >= config.power_user_hours
    week_of_row = day_week[d]
    n_weeks = int(day_week.max()) + 1
    week_flat = r * n_weeks + week_of_row
    per_week = (
        np.bincount(week_flat[qualifying], minlength=n_chunk * n_weeks)
        .reshape(n_chunk, n_weeks)
        .astype(np.int64)
    )
    power_weeks_matrix = per_week >= config.power_user_days

    # Attribute each power week to the month containing its first day.
    week_to_month = np.zeros(n_weeks, dtype=np.int64)
    for w in range(n_weeks):
        days_in_week = np.flatnonzero(day_week == w)
        week_to_month[w] = day_month[days_in_week[0]] if len(days_in_week) else 0
    power_weeks = np.zeros((n_chunk, months), dtype=np.int64)
    for w in range(n_weeks):
        power_weeks[:, week_to_month[w]] += power_weeks_matrix[:, w].astype(np.int64)

    return {
        "active_days": active_days,
        "hours_sum": hours_sum,
        "acceptance_sum": accept_sum,
        "sessions_sum": sessions_sum,
        "power_weeks": power_weeks,
    }
