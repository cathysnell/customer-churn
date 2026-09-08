"""The user population and its latent monthly engagement trajectories.

This module builds everything the churn model is *driven by*, before any
lifecycle decision is made:

* static user attributes (geo, persona, plan, signup date),
* a latent per-user **engagement index** per month — the single variable that
  makes coding hours, AI-acceptance and session frequency move together,
* per-month stickiness-feature adoption and support-friction intensity.

The engagement index is multiplicative and starts near ``1.0``:

    index[i, m] = exp(drift[i] * m + shock[i, m] + season[m])

``drift`` is the user's monthly log-drift, drawn from their (unpublished)
archetype. A negative drift is a user whose coding hours, acceptance rate and
session frequency all decay together — which is exactly the signal the churn
hazard in :mod:`datagen.hazard` reads. Nothing here decides who churns; it only
decides who *looks* like they might.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from datagen import reference as ref
from datagen.config import GeneratorConfig
from datagen.rng import choice_by_weight, substream, truncated_lognormal

# Fraction of the population that already existed before the observation window.
PRE_WINDOW_SHARE = 0.72

# Tenure (days) of pre-window users at window start: median ~ 1 year, capped 4y.
PRE_WINDOW_TENURE_MEDIAN_DAYS = 330.0
PRE_WINDOW_TENURE_SIGMA = 0.75
PRE_WINDOW_TENURE_MAX_DAYS = 1460.0

# Seasonality of developer activity, as a log-multiplier by calendar month
# (index 0 = January). Summer and December dips; spring/autumn peaks.
SEASONAL_LOG = np.array(
    [0.01, 0.03, 0.04, 0.02, 0.01, -0.03, -0.06, -0.05, 0.03, 0.05, 0.02, -0.09]
)

# Per-month idiosyncratic shock on the engagement index.
SHOCK_SIGMA = 0.085

# How strongly the engagement index moves acceptance / sessions / active days.
ACCEPTANCE_ELASTICITY = 0.16
SESSION_ELASTICITY = 0.70
ACTIVE_DAY_ELASTICITY = 0.55

PROGRAMMING_LANGUAGES: dict[str, float] = {
    "typescript": 0.24,
    "python": 0.23,
    "javascript": 0.14,
    "go": 0.10,
    "rust": 0.08,
    "java": 0.08,
    "c++": 0.06,
    "ruby": 0.04,
    "other": 0.03,
}

IDE_THEMES: dict[str, float] = {"dark": 0.74, "light": 0.18, "high_contrast": 0.08}


@dataclass(frozen=True)
class Population:
    """Latent state for every user, indexed consistently by row order.

    All 2-D arrays are ``(n_users, months)``. Row ``i`` of every array refers to
    the same user as ``user_id[i]`` — the pipeline relies on this alignment
    instead of joining on keys.
    """

    config: GeneratorConfig
    user_id: np.ndarray
    geo: np.ndarray
    country: np.ndarray
    persona: np.ndarray
    company_size: np.ndarray
    acquisition_channel: np.ndarray
    primary_language: np.ndarray
    ide_theme: np.ndarray
    archetype: np.ndarray
    plan_id: np.ndarray
    signup_date: np.ndarray  # datetime64[D]
    signup_day_index: np.ndarray  # offset into config.days; may be negative
    signup_month_index: np.ndarray  # offset into config.month_starts; may be negative

    # Per-user behavioural baselines.
    base_coding_hours: np.ndarray
    base_acceptance: np.ndarray
    base_sessions: np.ndarray
    base_active_day_prob: np.ndarray
    drift: np.ndarray

    # Per-user-per-month latent trajectories.
    engagement_index: np.ndarray
    month_coding_hours: np.ndarray
    month_acceptance: np.ndarray
    month_sessions: np.ndarray
    month_active_day_prob: np.ndarray

    # Per-user-per-month churn-relevant covariates.
    feature_first_month: np.ndarray  # (n_users, n_features); months, -1 = never
    features_adopted: np.ndarray  # (n_users, months) cumulative count
    support_intensity: np.ndarray  # (n_users, months) expected tickets
    support_tickets: np.ndarray  # (n_users, months) drawn ticket counts

    @property
    def n_users(self) -> int:
        return len(self.user_id)

    @property
    def months(self) -> int:
        return self.engagement_index.shape[1]

    def geo_attr(self, attr: str) -> np.ndarray:
        """Vector of geography attribute ``attr`` aligned to user rows."""
        lookup = {g.code: getattr(g, attr) for g in ref.GEOS}
        return np.array([lookup[code] for code in self.geo], dtype=float)


def build_population(config: GeneratorConfig) -> Population:
    """Draw the whole user population and its latent monthly trajectories."""
    n = config.n_users
    seed = config.seed

    ids = _user_ids(n)
    geo = choice_by_weight(substream(seed, "users.geo"), n, ref.GEO_SHARES)
    country = _countries(substream(seed, "users.country"), geo)
    persona = choice_by_weight(substream(seed, "users.persona"), n, ref.PERSONAS)
    company_size = choice_by_weight(
        substream(seed, "users.company_size"), n, ref.COMPANY_SIZE_BUCKETS
    )
    acquisition = choice_by_weight(
        substream(seed, "users.acquisition"), n, ref.ACQUISITION_CHANNELS
    )
    language = choice_by_weight(substream(seed, "users.language"), n, PROGRAMMING_LANGUAGES)
    theme = choice_by_weight(substream(seed, "users.theme"), n, IDE_THEMES)
    archetype = choice_by_weight(
        substream(seed, "users.archetype"), n, ref.ARCHETYPE_SHARES
    )
    plan_id = choice_by_weight(
        substream(seed, "users.plan"), n, {p.plan_id: p.share for p in ref.PLANS}
    )

    signup_date, signup_day_index, signup_month_index = _signup_dates(config)

    baselines = _baselines(config, archetype, geo)
    trajectories = _trajectories(config, baselines)
    adoption = _feature_adoption_months(config, baselines)
    support = _support_intensity(config, trajectories, geo, signup_month_index)

    return Population(
        config=config,
        user_id=ids,
        geo=geo,
        country=country,
        persona=persona,
        company_size=company_size,
        acquisition_channel=acquisition,
        primary_language=language,
        ide_theme=theme,
        archetype=archetype,
        plan_id=plan_id,
        signup_date=signup_date,
        signup_day_index=signup_day_index,
        signup_month_index=signup_month_index,
        base_coding_hours=baselines["coding_hours"],
        base_acceptance=baselines["acceptance"],
        base_sessions=baselines["sessions"],
        base_active_day_prob=baselines["active_day_prob"],
        drift=baselines["drift"],
        engagement_index=trajectories["engagement_index"],
        month_coding_hours=trajectories["coding_hours"],
        month_acceptance=trajectories["acceptance"],
        month_sessions=trajectories["sessions"],
        month_active_day_prob=trajectories["active_day_prob"],
        feature_first_month=adoption["first_month"],
        features_adopted=adoption["cumulative_count"],
        support_intensity=support["intensity"],
        support_tickets=support["tickets"],
        )


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def _user_ids(n: int) -> np.ndarray:
    """Stable, zero-padded surrogate keys. Not derived from anything real."""
    return np.array([f"USR-{i:08d}" for i in range(1, n + 1)], dtype=object)


def _countries(rng: np.random.Generator, geo: np.ndarray) -> np.ndarray:
    """Pick a country within each user's region (uniform within region)."""
    out = np.empty(len(geo), dtype=object)
    for code, region in ref.GEO_BY_CODE.items():
        mask = geo == code
        count = int(mask.sum())
        if count:
            picks = rng.integers(0, len(region.countries), size=count)
            out[mask] = np.array(region.countries, dtype=object)[picks]
    return out


def _signup_dates(config: GeneratorConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Draw signup dates: most users predate the window, the rest join during it.

    Returns the dates plus their offsets into ``config.days`` and
    ``config.month_starts``. Offsets are negative for pre-window signups, which
    is what marks a user as already-tenured on day 0.
    """
    n = config.n_users
    rng = substream(config.seed, "users.signup")
    is_pre = rng.random(n) < PRE_WINDOW_SHARE

    tenure = truncated_lognormal(
        rng,
        n,
        PRE_WINDOW_TENURE_MEDIAN_DAYS,
        PRE_WINDOW_TENURE_SIGMA,
        30.0,
        PRE_WINDOW_TENURE_MAX_DAYS,
    )
    # In-window signups are skewed early so they accrue enough history to churn.
    in_window = np.floor(rng.beta(1.6, 2.6, size=n) * (config.n_days - 45)).astype(np.int64)

    day_index = np.where(is_pre, -np.ceil(tenure).astype(np.int64), in_window)
    dates = (config.window_start + pd.to_timedelta(day_index, unit="D")).values.astype(
        "datetime64[D]"
    )

    month_starts = config.month_starts.values.astype("datetime64[M]")
    signup_month = dates.astype("datetime64[M]")
    month_index = (signup_month - month_starts[0]).astype(np.int64)
    return dates, day_index, month_index


def _archetype_attr(archetype: np.ndarray, attr: str) -> np.ndarray:
    lookup = {a.name: getattr(a, attr) for a in ref.ARCHETYPES}
    return np.array([lookup[name] for name in archetype], dtype=float)


def _baselines(
    config: GeneratorConfig, archetype: np.ndarray, geo: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-user baseline engagement levels, before any monthly drift."""
    n = config.n_users
    seed = config.seed

    geo_hours = np.array([ref.GEO_BY_CODE[g].hours_mult for g in geo], dtype=float)
    geo_accept = np.array([ref.GEO_BY_CODE[g].acceptance_offset for g in geo], dtype=float)
    geo_sessions = np.array([ref.GEO_BY_CODE[g].sessions_mult for g in geo], dtype=float)

    hours_median = _archetype_attr(archetype, "hours_median")
    hours_sigma = _archetype_attr(archetype, "hours_sigma")
    rng_hours = substream(seed, "population.base_hours")
    coding_hours = np.clip(
        hours_median * np.exp(rng_hours.normal(0.0, 1.0, size=n) * hours_sigma) * geo_hours,
        0.25,
        13.0,
    )

    rng_accept = substream(seed, "population.base_acceptance")
    acceptance = np.clip(
        _archetype_attr(archetype, "acceptance_mean")
        + geo_accept
        + rng_accept.normal(0.0, 0.055, size=n),
        0.05,
        0.90,
    )

    rng_sessions = substream(seed, "population.base_sessions")
    sessions = np.clip(
        _archetype_attr(archetype, "sessions_median")
        * np.exp(rng_sessions.normal(0.0, 0.28, size=n))
        * geo_sessions,
        0.6,
        18.0,
    )

    rng_active = substream(seed, "population.base_active_prob")
    active_prob = np.clip(
        _archetype_attr(archetype, "active_day_prob")
        + rng_active.normal(0.0, 0.06, size=n),
        0.05,
        0.99,
    )

    rng_drift = substream(seed, "population.drift")
    drift = _archetype_attr(archetype, "drift_mean") + rng_drift.normal(
        0.0, 1.0, size=n
    ) * _archetype_attr(archetype, "drift_sigma")

    return {
        "coding_hours": coding_hours,
        "acceptance": acceptance,
        "sessions": sessions,
        "active_day_prob": active_prob,
        "drift": drift,
    }


def _trajectories(
    config: GeneratorConfig, baselines: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Expand per-user baselines into per-month latent engagement levels."""
    n = config.n_users
    months = config.months
    month_idx = np.arange(months, dtype=float)[None, :]

    calendar_month = config.month_starts.month.values - 1
    season = SEASONAL_LOG[calendar_month][None, :]

    rng = substream(config.seed, "population.shocks")
    shocks = rng.normal(0.0, SHOCK_SIGMA, size=(n, months))
    # Smooth the shocks so a decline reads as a trend, not white noise.
    shocks = np.cumsum(shocks, axis=1) * 0.45 + shocks * 0.55

    log_index = baselines["drift"][:, None] * month_idx + shocks + season
    index = np.exp(np.clip(log_index, -3.0, 1.2))

    coding_hours = np.clip(baselines["coding_hours"][:, None] * index, 0.1, 15.0)
    acceptance = np.clip(
        baselines["acceptance"][:, None] + ACCEPTANCE_ELASTICITY * (index - 1.0),
        0.03,
        0.93,
    )
    sessions = np.clip(
        baselines["sessions"][:, None] * index**SESSION_ELASTICITY, 0.3, 20.0
    )
    active_prob = np.clip(
        baselines["active_day_prob"][:, None] * index**ACTIVE_DAY_ELASTICITY, 0.02, 0.99
    )

    return {
        "engagement_index": index,
        "coding_hours": coding_hours,
        "acceptance": acceptance,
        "sessions": sessions,
        "active_day_prob": active_prob,
    }


def _feature_adoption_months(
    config: GeneratorConfig, baselines: dict[str, np.ndarray]
) -> dict[str, np.ndarray]:
    """Decide, per user and feature, the month of first activation (or never).

    Adoption propensity rises with baseline coding hours: heavier users reach
    deeper into the product (so timing is driven by engagement *level*, not by
    the monthly trend). Activation month is then spread over the window so
    adoption accumulates rather than appearing fully formed on day one.
    """
    n = config.n_users
    months = config.months
    n_features = len(ref.FEATURES)
    rng = substream(config.seed, "population.feature_adoption")

    hours_z = (baselines["coding_hours"] - baselines["coding_hours"].mean()) / (
        baselines["coding_hours"].std() + 1e-9
    )
    first_month = np.full((n, n_features), -1, dtype=np.int64)

    for f_idx, feature in enumerate(ref.FEATURES):
        # Logit-shift base adoption by how heavy the user is.
        base_logit = np.log(feature.base_adoption / (1.0 - feature.base_adoption))
        prob = 1.0 / (1.0 + np.exp(-(base_logit + 0.62 * hours_z)))
        adopts = rng.random(n) < prob
        # Adopters activate early (most are already adopted at window start).
        when = np.floor(rng.beta(0.8, 2.4, size=n) * months).astype(np.int64)
        first_month[:, f_idx] = np.where(adopts, np.clip(when, 0, months - 1), -1)

    adopted = (first_month[:, :, None] >= 0) & (
        first_month[:, :, None] <= np.arange(months)[None, None, :]
    )
    cumulative = adopted.sum(axis=1).astype(np.int64)
    return {"first_month": first_month, "cumulative_count": cumulative}


def _support_intensity(
    config: GeneratorConfig,
    trajectories: dict[str, np.ndarray],
    geo: np.ndarray,
    signup_month_index: np.ndarray,
) -> dict[str, np.ndarray]:
    """Expected and realised monthly support-ticket counts.

    Friction rises when the engagement index falls (people file tickets when the
    product stops working for them) and in the first months after signup
    (onboarding questions), and varies by region.
    """
    months = config.months
    index = trajectories["engagement_index"]
    geo_mult = np.array([ref.GEO_BY_CODE[g].support_mult for g in geo], dtype=float)[:, None]

    decline = np.clip(1.0 - index, 0.0, 1.5)
    month_idx = np.arange(months)[None, :]
    tenure_months = month_idx - signup_month_index[:, None]
    onboarding = np.where((tenure_months >= 0) & (tenure_months <= 2), 0.10, 0.0)

    intensity = (0.055 + 0.42 * decline + onboarding) * geo_mult
    rng = substream(config.seed, "population.support_tickets")
    tickets = rng.poisson(intensity).astype(np.int64)
    return {"intensity": intensity, "tickets": tickets}
