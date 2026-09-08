"""Subscription lifecycle: the churn hazard, CRM touches and reactivation.

This is the causal core of the dataset. It walks the observation window one
month at a time and, for every user who is a subscriber on the first day of the
month, evaluates a **discrete-time churn hazard**:

    logit(p) = intercept + Σ β_k · x_k

The features ``x_k`` are read off the latent engagement trajectories built in
:mod:`datagen.population` — most importantly the *decline* in the engagement
index, which is what makes falling coding hours / AI-acceptance / session
frequency predict churn rather than merely coexist with it.

Two ordering rules keep the simulation causally honest:

* A CRM retention touch is decided at the **start** of a month, from state and
  decline known at that point, and then lowers that month's hazard. Touches are
  never assigned from an outcome that has not happened yet.
* Winback touches only reach users who are already lapsed, and a reactivation
  opens a new subscription term from a date inside the touch month.

``intercept`` is not hand-tuned: :func:`calibrate_intercept` bisects it until the
realised monthly churn rate matches ``config.monthly_churn_rate``. All random
draws are pre-generated once (see :class:`_Draws`), so the simulation is a pure,
monotone function of the intercept and the bisection is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from datagen import reference as ref
from datagen.config import GeneratorConfig
from datagen.population import Population
from datagen.rng import substream

# ---------------------------------------------------------------------------
# Hazard coefficients. Signs are the point of the whole dataset: declining
# engagement pushes churn UP, depth of use and tenure push it DOWN.
# ---------------------------------------------------------------------------

#: Month-over-month decline in the engagement index (positive = declining).
BETA_DECLINE_1M = 1.55
#: Three-month decline — captures a sustained slide, not a single bad month.
BETA_DECLINE_3M = 1.15
#: Level of coding hours (z-scored log). Negative: heavy users stay.
BETA_CODING_HOURS_LEVEL = -0.55
#: AI-suggestion acceptance rate, centred and scaled. Negative: it works for them.
BETA_ACCEPTANCE = -0.32
#: Session frequency (z-scored log). Negative: habitual users stay.
BETA_SESSION_FREQUENCY = -0.26
#: Support friction: each ticket in the month raises hazard.
BETA_SUPPORT_TICKETS = 0.22
#: Stickiness-weighted feature adoption. Negative: adoption is a moat.
BETA_STICKINESS = -0.85
#: Tenure, log-scaled. Negative: survivors keep surviving.
BETA_TENURE = -0.34
#: Weight on each region's configured churn shift.
BETA_GEO = 1.00
#: Annual billing lock-in, and team-plan stickiness.
BETA_ANNUAL_PLAN = -0.85
BETA_TEAM_PLAN = -0.25
#: Power-user engagement (expected qualifying days/week, scaled). Negative.
BETA_POWER_SCORE = -0.16
#: A delivered retention touch this month. Negative: this is the program effect.
BETA_RETENTION_TOUCH = -0.55
#: Payment failure in the month — involuntary churn pressure.
BETA_PAYMENT_FAILURE = 0.70

#: Hazard multiplier for a user in their first at-risk month after reactivation:
#: winbacks are fragile.
REACTIVATION_FRAGILITY_LOGIT = 0.65

#: Share of at-risk months that see a payment failure.
PAYMENT_FAILURE_RATE = 0.018

#: A lapsed user is winback-eligible for this many months after cancelling.
WINBACK_ELIGIBILITY_MONTHS = 3

#: At most this many reactivations per user, to keep term counts bounded.
MAX_REACTIVATIONS = 1

#: Decline threshold (month-over-month index ratio) that marks a user `at_risk`
#: for retention targeting and for `crm_touches.user_state_at_touch`.
AT_RISK_DECLINE_RATIO = 0.92

#: Probability a delivered touch is opened / clicked, by channel.
CHANNEL_OPEN_RATE = {"email": 0.34, "in_app": 0.62, "push": 0.41}
CHANNEL_CLICK_GIVEN_OPEN = {"email": 0.28, "in_app": 0.44, "push": 0.22}
CHANNEL_DELIVERY_RATE = {"email": 0.96, "in_app": 0.995, "push": 0.88}
CHANNEL_COST_USD = {"email": 0.04, "in_app": 0.01, "push": 0.02}
#: Unsubscribe probability for a non-converting touch.
UNSUBSCRIBE_RATE = 0.012

#: Bisection bounds and step count for intercept calibration.
CALIBRATION_LO = -12.0
CALIBRATION_HI = 4.0
CALIBRATION_STEPS = 34
CALIBRATION_TOLERANCE = 1e-4

# User lifecycle states.
_NOT_YET = 0
_SUBSCRIBER = 1
_LAPSED = 2


@dataclass(frozen=True)
class _Draws:
    """Pre-generated random draws, so the sim is deterministic given an intercept.

    Bisecting the intercept re-runs the simulation many times; if the draws were
    taken inside the loop, each candidate would see different randomness and the
    realised churn rate would not be monotone in the intercept.
    """

    churn_u: np.ndarray  # (n, months) hazard comparison uniforms
    churn_day: np.ndarray  # (n, months) day-within-month position in [0, 1)
    payment_failure: np.ndarray  # (n, months) bool
    retention_target_u: np.ndarray  # (n, months, n_campaigns)
    touch_delivered_u: np.ndarray
    touch_open_u: np.ndarray
    touch_click_u: np.ndarray
    touch_outcome_u: np.ndarray
    touch_unsub_u: np.ndarray
    touch_variant: np.ndarray  # (n, months, n_campaigns) index into MESSAGE_VARIANTS
    touch_day: np.ndarray
    downgrade_u: np.ndarray  # (n, months)
    cancel_reason: np.ndarray  # (n,) index into CANCEL_REASONS
    cancel_reason_2: np.ndarray  # (n,) reason for a post-reactivation cancellation


@dataclass(frozen=True)
class Lifecycle:
    """Outcome of the lifecycle simulation.

    All matrices are ``(n_users, months)`` aligned to :class:`Population` rows.
    """

    config: GeneratorConfig
    intercept: float
    realised_monthly_churn_rate: float
    calibration_iterations: int

    at_risk: np.ndarray  # bool: subscriber on the first day of the month
    churned: np.ndarray  # bool: cancelled during the month
    hazard: np.ndarray  # float: modelled churn probability for at-risk months
    churn_day_index: np.ndarray  # int: day offset of first cancellation, -1 if none
    churn2_day_index: np.ndarray  # int: day offset of post-winback cancellation, -1 if none
    #: (n_users, months) day offset of the cancellation recorded in that month,
    #: -1 where the user did not churn. Lets churn_labels date each event exactly.
    churn_day_by_month: np.ndarray
    reactivated_month: np.ndarray  # int: month of reactivation, -1 if none
    reactivation_day_index: np.ndarray
    downgrade_month: np.ndarray  # int: month of downgrade, -1 if none
    downgrade_day_index: np.ndarray
    payment_failures: np.ndarray  # int per month
    cancel_reason: np.ndarray  # object: reason code per user, None if never
    cancel_reason_2: np.ndarray  # object: reason for the second cancellation
    #: Per-user-per-month subscriber mask for the *whole* month span (used to
    #: mask daily usage): TRUE if the user was a subscriber at any point.
    subscriber_month: np.ndarray
    #: Day-resolution subscription mask, (n_users, n_days).
    subscribed_day: np.ndarray
    touches: pd.DataFrame  # long-form touch log (see schemas.CRM_TOUCHES)
    retention_touch_month: np.ndarray  # int count of retention touches per month


def simulate(population: Population) -> Lifecycle:
    """Calibrate the hazard intercept and run the final lifecycle simulation."""
    config = population.config
    features = build_features(population)
    draws = _build_draws(config)

    intercept, iterations = calibrate_intercept(population, features, draws)
    result = _run(population, features, draws, intercept)
    rate = _rate(result)
    return Lifecycle(
        config=config,
        intercept=intercept,
        realised_monthly_churn_rate=rate,
        calibration_iterations=iterations,
        **result,
    )


# ---------------------------------------------------------------------------
# Hazard features
# ---------------------------------------------------------------------------


def build_features(population: Population) -> dict[str, np.ndarray]:
    """Assemble the ``(n_users, months)`` hazard covariates from latent state.

    Kept separate from :func:`_run` so calibration reuses one computation.
    """
    index = population.engagement_index
    months = population.months

    # Decline: positive when the engagement index is falling. Month 0 has no
    # prior month, so it is treated as flat rather than fabricated.
    prev_1 = np.concatenate([index[:, :1], index[:, :-1]], axis=1)
    lag = min(3, months - 1) or 1
    prev_3 = np.concatenate([np.repeat(index[:, :1], lag, axis=1), index[:, :-lag]], axis=1)
    decline_1m = np.clip(-np.log(index / np.maximum(prev_1, 1e-6)), -1.0, 2.0)
    decline_3m = np.clip(-np.log(index / np.maximum(prev_3, 1e-6)), -1.0, 2.5)

    hours = population.month_coding_hours
    log_hours = np.log(np.maximum(hours, 0.1))
    hours_z = (log_hours - log_hours.mean()) / (log_hours.std() + 1e-9)

    acceptance_z = (population.month_acceptance - 0.35) / 0.10

    log_sessions = np.log(np.maximum(population.month_sessions, 0.1))
    sessions_z = (log_sessions - log_sessions.mean()) / (log_sessions.std() + 1e-9)

    stickiness = _stickiness_weight(population)

    month_idx = np.arange(months)[None, :]
    tenure_months = np.maximum(month_idx - population.signup_month_index[:, None], 0)
    tenure_term = np.log1p(tenure_months) / np.log(13.0)

    geo_logit = population.geo_attr("churn_logit")[:, None] * np.ones((1, months))

    is_annual = (population.plan_id == "pro_annual").astype(float)[:, None]
    is_team = (population.plan_id == "pro_team_monthly").astype(float)[:, None]

    return {
        "decline_1m": decline_1m,
        "decline_3m": decline_3m,
        "hours_z": hours_z,
        "acceptance_z": acceptance_z,
        "sessions_z": sessions_z,
        "support_tickets": population.support_tickets.astype(float),
        "stickiness": stickiness,
        "tenure_term": tenure_term,
        "geo_logit": geo_logit,
        "is_annual": is_annual * np.ones((1, months)),
        "is_team": is_team * np.ones((1, months)),
        "power_score": power_score(population),
        "tenure_months": tenure_months,
        "decline_ratio": index / np.maximum(prev_1, 1e-6),
    }


def _stickiness_weight(population: Population) -> np.ndarray:
    """Stickiness-weighted count of features adopted, per user per month."""
    months = population.months
    first_month = population.feature_first_month
    weights = np.array([f.stickiness for f in ref.FEATURES], dtype=float)
    adopted = (first_month[:, :, None] >= 0) & (
        first_month[:, :, None] <= np.arange(months)[None, None, :]
    )
    return np.tensordot(weights, adopted, axes=([0], [1]))


def power_score(population: Population) -> np.ndarray:
    """Expected days/week meeting the power-user bar, per user per month.

    A *continuous* latent proxy, deliberately not the published
    ``users.power_user_flag`` — that flag is measured from the emitted daily
    rows in :mod:`datagen.usage`. Using a continuous proxy here avoids feeding
    the hazard a variable that the daily generator has not produced yet.
    """
    from datagen.usage import DAILY_HOURS_LOG_SIGMA

    config = population.config
    mu = np.log(np.maximum(population.month_coding_hours, 0.05))
    # P(lognormal(mu, sigma) >= bar) via the normal survival function.
    z = (np.log(config.power_user_hours) - mu) / DAILY_HOURS_LOG_SIGMA
    p_over_bar = 0.5 * (1.0 - _erf(z / np.sqrt(2.0)))
    return 7.0 * population.month_active_day_prob * p_over_bar


def _erf(x: np.ndarray) -> np.ndarray:
    """Abramowitz & Stegun 7.1.26 error function (avoids a scipy dependency)."""
    sign = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (
        (
            (
                ((1.061405429 * t - 1.453152027) * t) + 1.421413741
            )
            * t
            - 0.284496736
        )
        * t
        + 0.254829592
    ) * t * np.exp(-x * x)
    return sign * y


# ---------------------------------------------------------------------------
# Draws
# ---------------------------------------------------------------------------


def _build_draws(config: GeneratorConfig) -> _Draws:
    n, months = config.n_users, config.months
    n_campaigns = config.campaigns
    shape = (n, months)
    tshape = (n, months, n_campaigns)

    return _Draws(
        churn_u=substream(config.seed, "lifecycle.churn").random(shape),
        churn_day=substream(config.seed, "lifecycle.churn_day").random(shape),
        payment_failure=(
            substream(config.seed, "lifecycle.payment_failure").random(shape)
            < PAYMENT_FAILURE_RATE
        ),
        retention_target_u=substream(config.seed, "crm.target").random(tshape),
        touch_delivered_u=substream(config.seed, "crm.delivered").random(tshape),
        touch_open_u=substream(config.seed, "crm.open").random(tshape),
        touch_click_u=substream(config.seed, "crm.click").random(tshape),
        touch_outcome_u=substream(config.seed, "crm.outcome").random(tshape),
        touch_unsub_u=substream(config.seed, "crm.unsub").random(tshape),
        touch_variant=substream(config.seed, "crm.variant").integers(
            0, len(ref.MESSAGE_VARIANTS), size=tshape
        ),
        touch_day=substream(config.seed, "crm.touch_day").random(tshape),
        downgrade_u=substream(config.seed, "lifecycle.downgrade").random(shape),
        cancel_reason=substream(config.seed, "lifecycle.cancel_reason").choice(
            len(ref.CANCEL_REASONS),
            size=n,
            p=_normalised(list(ref.CANCEL_REASONS.values())),
        ),
        cancel_reason_2=substream(config.seed, "lifecycle.cancel_reason_2").choice(
            len(ref.CANCEL_REASONS),
            size=n,
            p=_normalised(list(ref.CANCEL_REASONS.values())),
        ),
    )


def _normalised(values: list[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    return arr / arr.sum()


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


def calibrate_intercept(
    population: Population,
    features: dict[str, np.ndarray],
    draws: _Draws,
    *,
    collect_touches: bool = False,
) -> tuple[float, int]:
    """Bisect the hazard intercept until realised monthly churn hits the target.

    The realised rate is monotone increasing in the intercept (every hazard is
    monotone in it and the draws are fixed), so plain bisection converges. The
    step count is fixed rather than tolerance-driven so two runs of the same
    config perform the same number of iterations.

    Returns:
        ``(intercept, iterations_used)``.
    """
    target = population.config.monthly_churn_rate
    lo, hi = CALIBRATION_LO, CALIBRATION_HI
    best = lo
    iterations = 0

    for _ in range(CALIBRATION_STEPS):
        iterations += 1
        mid = 0.5 * (lo + hi)
        rate = _rate(_run(population, features, draws, mid, collect_touches=collect_touches))
        best = mid
        if abs(rate - target) < CALIBRATION_TOLERANCE:
            break
        if rate < target:
            lo = mid
        else:
            hi = mid
    return best, iterations


def _rate(result: dict[str, np.ndarray]) -> float:
    at_risk = result["at_risk"]
    total = int(at_risk.sum())
    if total == 0:
        return 0.0
    return float(result["churned"].sum()) / total


# ---------------------------------------------------------------------------
# The simulation
# ---------------------------------------------------------------------------


def _run(
    population: Population,
    features: dict[str, np.ndarray],
    draws: _Draws,
    intercept: float,
    *,
    collect_touches: bool = True,
) -> dict[str, object]:
    """Walk the window month by month. Pure given ``(features, draws, intercept)``."""
    config = population.config
    n, months = population.n_users, population.months

    state = np.where(population.signup_month_index < 0, _SUBSCRIBER, _NOT_YET)
    at_risk = np.zeros((n, months), dtype=bool)
    churned = np.zeros((n, months), dtype=bool)
    hazard = np.zeros((n, months), dtype=float)
    churn_day_index = np.full(n, -1, dtype=np.int64)
    churn_month = np.full(n, -1, dtype=np.int64)
    # A won-back user can churn a second time. That is a distinct event with its
    # own term boundary, so it is tracked separately instead of overwriting the
    # first cancellation (which would corrupt the subscription term history).
    churn2_day_index = np.full(n, -1, dtype=np.int64)
    churn_day_by_month = np.full((n, months), -1, dtype=np.int64)
    reactivated_month = np.full(n, -1, dtype=np.int64)
    reactivation_day_index = np.full(n, -1, dtype=np.int64)
    downgrade_month = np.full(n, -1, dtype=np.int64)
    downgrade_day_index = np.full(n, -1, dtype=np.int64)
    payment_failures = np.zeros((n, months), dtype=np.int64)
    reactivations = np.zeros(n, dtype=np.int64)
    subscriber_month = np.zeros((n, months), dtype=bool)
    retention_touch_month = np.zeros((n, months), dtype=np.int64)
    just_reactivated = np.zeros(n, dtype=bool)
    unsubscribed = np.zeros(n, dtype=bool)
    # Day offsets: subscription starts/stops within the window, per user.
    sub_start_day = np.where(
        population.signup_day_index < 0, 0, population.signup_day_index
    ).astype(np.int64)

    touch_rows: list[dict[str, object]] = []
    month_first_day = _month_first_day_index(config)
    month_len = _month_lengths(config)

    base_logit = _base_logit(features, intercept)

    for m in range(months):
        # -- state entry: users whose signup month has passed become subscribers
        newly = (state == _NOT_YET) & (population.signup_month_index < m)
        state = np.where(newly, _SUBSCRIBER, state)

        month_at_risk = state == _SUBSCRIBER
        at_risk[:, m] = month_at_risk

        # -- CRM touches decided from state known at the START of the month
        decline_ratio = features["decline_ratio"][:, m]
        user_state = np.where(
            month_at_risk,
            np.where(decline_ratio < AT_RISK_DECLINE_RATIO, "at_risk", "active"),
            np.where(state == _LAPSED, "lapsed", "not_subscribed"),
        )
        # Winback-eligible: lapsed within the eligibility window AND not already
        # at the reactivation cap. Excluding capped users here means we never send
        # a touch that could not possibly convert, rather than sending one and
        # suppressing the conversion later.
        lapsed_recently = (
            (state == _LAPSED)
            & (churn_month >= 0)
            & ((m - churn_month) <= WINBACK_ELIGIBILITY_MONTHS)
            & (reactivations < MAX_REACTIVATIONS)
        )

        touched_retention = np.zeros(n, dtype=bool)
        # Accumulated hazard reduction from retention touches this month. A
        # campaign with lift 1.45 (the power-user concierge) bends the hazard
        # harder than the generic nudge, so `lift` is a real modelled effect for
        # retention campaigns rather than metadata.
        retention_effect = np.zeros(n, dtype=float)
        reactivate_now = np.zeros(n, dtype=bool)
        reactivate_touch_day = np.zeros(n, dtype=float)

        for c_idx, campaign in enumerate(ref.CAMPAIGNS[: config.campaigns]):
            live = campaign.month_offset <= m < campaign.month_offset + campaign.duration_months
            if not live:
                continue
            eligible = _eligible(
                campaign,
                population,
                features,
                m,
                month_at_risk,
                lapsed_recently,
                unsubscribed,
            )
            selected = eligible & (draws.retention_target_u[:, m, c_idx] < campaign.reach)
            if not selected.any():
                continue

            delivered = selected & (
                draws.touch_delivered_u[:, m, c_idx] < CHANNEL_DELIVERY_RATE[campaign.channel]
            )
            if campaign.objective == "retention":
                touched_retention |= delivered
                # Take the strongest touch rather than summing, so stacking two
                # campaigns on one user cannot drive the hazard to zero.
                retention_effect = np.maximum(
                    retention_effect, delivered * campaign.lift
                )

            # Only a winback touch can *reactivate* anyone: reactivation means a
            # lapsed user resubscribing. A retention/adoption/expansion touch
            # acts on an already-active user, and its effect is the hazard
            # reduction below (BETA_RETENTION_TOUCH) — never a reactivation. So
            # `outcome == 'reactivated'` means exactly one thing everywhere.
            converted = np.zeros(n, dtype=bool)
            if campaign.objective == "winback":
                converted = delivered & (
                    draws.touch_outcome_u[:, m, c_idx]
                    < np.clip(config.reactivation_rate * campaign.lift, 0.0, 0.95)
                )
                # Enforce MAX_REACTIVATIONS. Without this cap a user could be won
                # back repeatedly across months: each conversion would overwrite
                # the prior reactivation date and the single second-churn date,
                # while `subscriptions` (A03) only ever emits one reactivation
                # term — leaving reactivated touches with no corresponding
                # billing term. Capping keeps lifecycle state, A03 terms and
                # touch outcomes mutually consistent.
                converted &= reactivations < MAX_REACTIVATIONS
                # First campaign to convert a given user this month wins.
                converted &= ~reactivate_now
                reactivate_now |= converted
                reactivate_touch_day = np.where(
                    converted, draws.touch_day[:, m, c_idx], reactivate_touch_day
                )

            if collect_touches:
                touch_rows.append(
                    _touch_batch(
                        config,
                        population,
                        campaign,
                        c_idx,
                        m,
                        selected,
                        delivered,
                        converted,
                        user_state,
                        draws,
                        month_first_day[m],
                        month_len[m],
                    )
                )
            # Non-converting touches can burn the channel for that user.
            unsubscribed |= delivered & ~converted & (
                draws.touch_unsub_u[:, m, c_idx] < UNSUBSCRIBE_RATE
            )

        retention_touch_month[:, m] = touched_retention.astype(np.int64)

        # -- hazard for at-risk users
        logit = base_logit[:, m].copy()
        logit += BETA_RETENTION_TOUCH * retention_effect
        logit += REACTIVATION_FRAGILITY_LOGIT * just_reactivated
        failure = draws.payment_failure[:, m] & month_at_risk
        payment_failures[:, m] = failure.astype(np.int64)
        logit += BETA_PAYMENT_FAILURE * failure

        p = 1.0 / (1.0 + np.exp(-logit))
        hazard[:, m] = np.where(month_at_risk, p, 0.0)

        churn_now = month_at_risk & (draws.churn_u[:, m] < p)
        churned[:, m] = churn_now

        # Cancellation lands on a day inside the month.
        day_in_month = np.floor(draws.churn_day[:, m] * month_len[m]).astype(np.int64)
        cancel_day = np.minimum(month_first_day[m] + day_in_month, config.n_days - 1)
        # A user cannot cancel before they signed up, nor before a reactivation
        # that is already on the books.
        cancel_day = np.maximum(cancel_day, sub_start_day)
        is_second = churn_now & (reactivated_month >= 0)
        cancel_day = np.where(
            is_second, np.maximum(cancel_day, reactivation_day_index), cancel_day
        )
        churn2_day_index = np.where(is_second, cancel_day, churn2_day_index)
        first_churn = churn_now & ~is_second
        churn_day_index = np.where(first_churn, cancel_day, churn_day_index)
        # Per-month churn day, so churn_labels can date each event in the month it
        # belongs to. Using the scalar first-churn day would mis-date the second
        # cancellation of a won-back user.
        churn_day_by_month[:, m] = np.where(churn_now, cancel_day, -1)
        churn_month = np.where(churn_now, m, churn_month)
        state = np.where(churn_now, _LAPSED, state)

        # -- downgrades: a mid-life plan change, only for surviving subscribers
        can_downgrade = (
            month_at_risk
            & ~churn_now
            & (downgrade_month < 0)
            & (population.plan_id != "pro_monthly")
            & (features["decline_ratio"][:, m] < 1.0)
        )
        downgrade_now = can_downgrade & (draws.downgrade_u[:, m] < 0.012)
        d_day = np.minimum(
            month_first_day[m] + np.floor(draws.downgrade_u[:, m] * month_len[m]).astype(np.int64),
            config.n_days - 1,
        )
        downgrade_day_index = np.where(
            downgrade_now, np.maximum(d_day, sub_start_day), downgrade_day_index
        )
        downgrade_month = np.where(downgrade_now, m, downgrade_month)

        # -- reactivation from a winback conversion
        if reactivate_now.any():
            r_day = np.minimum(
                month_first_day[m]
                + np.floor(reactivate_touch_day * month_len[m]).astype(np.int64),
                config.n_days - 1,
            )
            reactivated_month = np.where(reactivate_now, m, reactivated_month)
            reactivation_day_index = np.where(reactivate_now, r_day, reactivation_day_index)
            reactivations = reactivations + reactivate_now.astype(np.int64)
            state = np.where(reactivate_now, _SUBSCRIBER, state)

        just_reactivated = reactivate_now
        subscriber_month[:, m] = month_at_risk | reactivate_now

    cancel_reason = _cancel_reasons(draws.cancel_reason, churn_day_index)
    cancel_reason_2 = _cancel_reasons(draws.cancel_reason_2, churn2_day_index)
    subscribed_day = _daily_mask(
        config,
        sub_start_day,
        churn_day_index,
        reactivation_day_index,
        churn2_day_index,
    )

    return {
        "at_risk": at_risk,
        "churned": churned,
        "hazard": hazard,
        "churn_day_index": churn_day_index,
        "churn2_day_index": churn2_day_index,
        "churn_day_by_month": churn_day_by_month,
        "cancel_reason_2": cancel_reason_2,
        "reactivated_month": reactivated_month,
        "reactivation_day_index": reactivation_day_index,
        "downgrade_month": downgrade_month,
        "downgrade_day_index": downgrade_day_index,
        "payment_failures": payment_failures,
        "cancel_reason": cancel_reason,
        "subscriber_month": subscriber_month,
        "subscribed_day": subscribed_day,
        "touches": _concat_touches(touch_rows),
        "retention_touch_month": retention_touch_month,
    }


def _base_logit(features: dict[str, np.ndarray], intercept: float) -> np.ndarray:
    """The intercept plus every covariate that does not depend on the month loop."""
    return (
        intercept
        + BETA_DECLINE_1M * features["decline_1m"]
        + BETA_DECLINE_3M * features["decline_3m"]
        + BETA_CODING_HOURS_LEVEL * features["hours_z"]
        + BETA_ACCEPTANCE * features["acceptance_z"]
        + BETA_SESSION_FREQUENCY * features["sessions_z"]
        + BETA_SUPPORT_TICKETS * features["support_tickets"]
        + BETA_STICKINESS * features["stickiness"]
        + BETA_TENURE * features["tenure_term"]
        + BETA_GEO * features["geo_logit"]
        + BETA_ANNUAL_PLAN * features["is_annual"]
        + BETA_TEAM_PLAN * features["is_team"]
        + BETA_POWER_SCORE * features["power_score"]
    )


def _eligible(
    campaign: ref.Campaign,
    population: Population,
    features: dict[str, np.ndarray],
    month: int,
    month_at_risk: np.ndarray,
    lapsed_recently: np.ndarray,
    unsubscribed: np.ndarray,
) -> np.ndarray:
    """Who this campaign may touch this month, per its ``target_segment`` rule."""
    declining = features["decline_ratio"][:, month] < AT_RISK_DECLINE_RATIO
    heavy = features["power_score"][:, month] >= population.config.power_user_days

    if campaign.target_segment == "declining_engagement_active":
        eligible = month_at_risk & declining
    elif campaign.target_segment == "declining_engagement_power_user":
        eligible = month_at_risk & declining & heavy
    elif campaign.target_segment == "lapsed_within_90d":
        eligible = lapsed_recently
    elif campaign.target_segment == "low_feature_adoption_active":
        eligible = month_at_risk & (population.features_adopted[:, month] <= 2)
    elif campaign.target_segment == "engaged_monthly_billers":
        eligible = (
            month_at_risk
            & ~declining
            & np.isin(population.plan_id, ["pro_monthly", "pro_team_monthly"])
        )
    else:  # pragma: no cover - guarded by the Campaign definitions above
        raise ValueError(f"unknown target_segment {campaign.target_segment!r}")

    # An email/push unsubscribe suppresses further outbound on those channels.
    if campaign.channel in ("email", "push"):
        eligible = eligible & ~unsubscribed
    return eligible


def _touch_batch(
    config: GeneratorConfig,
    population: Population,
    campaign: ref.Campaign,
    campaign_index: int,
    month: int,
    selected: np.ndarray,
    delivered: np.ndarray,
    converted: np.ndarray,
    user_state: np.ndarray,
    draws: _Draws,
    month_first_day: int,
    month_len: int,
) -> dict[str, np.ndarray]:
    """Build the touch rows for one campaign in one month as column arrays."""
    idx = np.flatnonzero(selected)
    delivered_s = delivered[idx]
    converted_s = converted[idx]

    open_p = CHANNEL_OPEN_RATE[campaign.channel]
    click_p = CHANNEL_CLICK_GIVEN_OPEN[campaign.channel]
    opened = delivered_s & (draws.touch_open_u[idx, month, campaign_index] < open_p)
    # A conversion implies the user engaged with the message.
    opened = opened | converted_s
    clicked = opened & (draws.touch_click_u[idx, month, campaign_index] < click_p)
    clicked = clicked | converted_s

    unsub = (
        delivered_s
        & ~converted_s
        & (draws.touch_unsub_u[idx, month, campaign_index] < UNSUBSCRIBE_RATE)
    )
    outcome = np.where(
        converted_s,
        "reactivated",
        np.where(
            unsub,
            "unsubscribed",
            np.where(clicked | opened, "engaged_no_conversion", "no_response"),
        ),
    )
    outcome = np.where(delivered_s, outcome, "no_response")

    day = np.minimum(
        month_first_day
        + np.floor(draws.touch_day[idx, month, campaign_index] * month_len).astype(np.int64),
        config.n_days - 1,
    )
    return {
        "campaign_id": np.full(len(idx), campaign.campaign_id, dtype=object),
        "user_id": population.user_id[idx],
        "touch_day_index": day,
        "channel": np.full(len(idx), campaign.channel, dtype=object),
        "message_variant": np.array(ref.MESSAGE_VARIANTS, dtype=object)[
            draws.touch_variant[idx, month, campaign_index]
        ],
        "delivered": delivered_s,
        "opened": opened & delivered_s,
        "clicked": clicked & delivered_s,
        "outcome": outcome.astype(object),
        "reactivated": converted_s,
        "user_state_at_touch": user_state[idx].astype(object),
        "cost_usd": np.full(len(idx), CHANNEL_COST_USD[campaign.channel], dtype=float),
    }


def _concat_touches(batches: list[dict[str, object]]) -> pd.DataFrame:
    if not batches:
        return pd.DataFrame(columns=list(_TOUCH_COLUMNS))
    return pd.DataFrame({key: np.concatenate([b[key] for b in batches]) for key in batches[0]})


_TOUCH_COLUMNS = (
    "campaign_id",
    "user_id",
    "touch_day_index",
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


def _month_first_day_index(config: GeneratorConfig) -> np.ndarray:
    """Day offset (into ``config.days``) of the first day of each month."""
    return ((config.month_starts - config.window_start).days).to_numpy()


def _month_lengths(config: GeneratorConfig) -> np.ndarray:
    """Number of days in each month of the window, truncated at ``window_end``."""
    starts = config.month_starts
    ends = starts + pd.offsets.MonthEnd(0)
    ends = ends.where(ends <= config.window_end, config.window_end)
    return ((ends - starts).days + 1).to_numpy()


def _cancel_reasons(picks: np.ndarray, churn_day_index: np.ndarray) -> np.ndarray:
    """Map reason indices to labels, leaving ``None`` where no cancellation happened."""
    reasons = np.array(list(ref.CANCEL_REASONS.keys()), dtype=object)
    return np.where(churn_day_index >= 0, reasons[picks], None)


def _daily_mask(
    config: GeneratorConfig,
    sub_start_day: np.ndarray,
    churn_day_index: np.ndarray,
    reactivation_day_index: np.ndarray,
    churn2_day_index: np.ndarray,
) -> np.ndarray:
    """Day-resolution ``(n_users, n_days)`` mask of "was a paying subscriber".

    A user is subscribed from signup (or day 0 if they predate the window) up to
    and including their cancellation day, and again from a reactivation day up to
    a second cancellation if one occurred. This is what stops usage rows
    appearing during a lapse.
    """
    days = np.arange(config.n_days)[None, :]
    started = days >= np.maximum(sub_start_day, 0)[:, None]

    churn = churn_day_index[:, None]
    first_span = started & ((churn < 0) | (days <= churn))

    react = reactivation_day_index[:, None]
    churn2 = churn2_day_index[:, None]
    second_span = (react >= 0) & (days >= react) & ((churn2 < 0) | (days <= churn2))
    return first_span | second_span
