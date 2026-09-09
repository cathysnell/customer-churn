"""The realism levers from the brief, asserted as properties of the data.

The brief requires that **declining coding hours, falling AI-suggestion
acceptance and dropping session frequency correlate with higher churn
propensity**, plus geographic variation and a power-user segment. If any of
these stops holding, the downstream ML stage would be training on noise, so
these are treated as correctness tests rather than nice-to-haves.
"""

from __future__ import annotations

import pytest

from datagen.config import GeneratorConfig
from datagen.pipeline import (
    GenerationResult,
    churn_signal_summary,
    generate,
    geo_summary,
)


@pytest.fixture(scope="module")
def signal(result: GenerationResult):
    return churn_signal_summary(result)


def test_churned_users_have_lower_late_window_coding_hours(signal) -> None:
    """THE headline correlation: churners code materially less late in life."""
    churned = signal.loc["churned", "avg_coding_hours"]
    retained = signal.loc["retained", "avg_coding_hours"]
    assert churned < retained, f"churned={churned} retained={retained}"
    # Require a real gap, not a rounding-level difference.
    assert churned < 0.85 * retained


def test_churned_users_have_lower_ai_acceptance(signal) -> None:
    churned = signal.loc["churned", "avg_acceptance_rate"]
    retained = signal.loc["retained", "avg_acceptance_rate"]
    assert churned < retained
    assert churned < 0.95 * retained


def test_churned_users_have_lower_session_frequency(signal) -> None:
    churned = signal.loc["churned", "avg_session_frequency"]
    retained = signal.loc["retained", "avg_session_frequency"]
    assert churned < retained
    assert churned < 0.9 * retained


def test_churned_users_have_fewer_active_days(signal) -> None:
    assert signal.loc["churned", "avg_active_days"] < signal.loc["retained", "avg_active_days"]


def test_churned_users_show_a_declining_trend(signal) -> None:
    """Churners' month-over-month coding-hours trend is below the retained cohort."""
    churned = signal.loc["churned", "avg_coding_hours_trend"]
    retained = signal.loc["retained", "avg_coding_hours_trend"]
    assert churned < retained
    assert churned < 1.0, "churners should be trending down, not flat"


def test_behavioural_features_are_negatively_correlated_with_churn(
    result: GenerationResult,
) -> None:
    """Each engagement feature must have a real negative correlation with the label."""
    labels = result.frames["churn_labels"]
    target = labels["churned"].astype(float)

    for column, ceiling in [
        ("avg_coding_hours", -0.05),
        ("avg_acceptance_rate", -0.05),
        ("avg_session_frequency", -0.05),
        ("active_days", -0.10),
        ("coding_hours_trend_30d", -0.02),
    ]:
        correlation = labels[column].corr(target)
        assert correlation < ceiling, f"{column} correlation with churn is {correlation:.4f}"


def test_support_friction_is_positively_correlated_with_churn(
    result: GenerationResult,
) -> None:
    """A14 support volume is meant to be a churn signal, not decoration."""
    labels = result.frames["churn_labels"]
    correlation = labels["support_tickets_30d"].corr(labels["churned"].astype(float))
    assert correlation > 0.0, f"support ticket correlation is {correlation:.4f}"


def test_feature_adoption_is_negatively_correlated_with_churn(
    result: GenerationResult,
) -> None:
    """A07 stickiness adoption should suppress churn."""
    labels = result.frames["churn_labels"]
    correlation = labels["features_adopted"].corr(labels["churned"].astype(float))
    assert correlation < 0.0, f"feature adoption correlation is {correlation:.4f}"


def test_churn_rate_rises_as_coding_hours_trend_falls(result: GenerationResult) -> None:
    """Steeply declining users churn more than growing users, by a wide margin."""
    labels = result.frames["churn_labels"]
    declining = labels[labels["coding_hours_trend_30d"] < 0.75]
    growing = labels[labels["coding_hours_trend_30d"] >= 1.0]

    assert len(declining) > 50 and len(growing) > 50, "not enough rows to compare"
    assert declining["churned"].mean() > growing["churned"].mean()


def test_power_users_churn_less_than_non_power_users(result: GenerationResult) -> None:
    """The power-user segment must actually be the sticky one."""
    labels = result.frames["churn_labels"].merge(
        result.frames["users"][["user_id", "power_user_flag"]], on="user_id"
    )
    power = labels[labels["power_user_flag"]]["churned"].mean()
    rest = labels[~labels["power_user_flag"]]["churned"].mean()
    assert power < rest, f"power={power:.4f} rest={rest:.4f}"


# ---------------------------------------------------------------------------
# Churn rate band
# ---------------------------------------------------------------------------


def test_monthly_churn_rate_matches_configured_target(result: GenerationResult) -> None:
    """Calibration must land the realised rate on the brief's 4.7% baseline."""
    rate = result.monthly_churn_rate
    target = result.config.monthly_churn_rate
    assert rate == pytest.approx(target, abs=0.005), f"rate={rate:.4f} target={target:.4f}"


def test_monthly_churn_rate_is_in_a_sane_band(result: GenerationResult) -> None:
    """A hard sanity band independent of the target: SaaS churn is a few percent."""
    rate = result.monthly_churn_rate
    assert 0.01 < rate < 0.12, f"monthly churn rate {rate:.4f} is not plausible"


def test_churn_rate_is_tunable(tiny_config: GeneratorConfig) -> None:
    """The base rate is a real knob: raising the target raises realised churn."""
    low = generate(tiny_config.replace(monthly_churn_rate=0.02))
    high = generate(tiny_config.replace(monthly_churn_rate=0.09))

    assert low.monthly_churn_rate < high.monthly_churn_rate
    assert low.monthly_churn_rate == pytest.approx(0.02, abs=0.01)
    assert high.monthly_churn_rate == pytest.approx(0.09, abs=0.01)


def test_no_month_has_absurd_churn(result: GenerationResult) -> None:
    """Guards against a calibration that hits the mean via wild monthly swings."""
    labels = result.frames["churn_labels"]
    per_month = labels.groupby("month_start")["churned"].mean()
    assert per_month.max() < 0.25, f"worst month churned {per_month.max():.3f}"


# ---------------------------------------------------------------------------
# Geographic variation and the power-user segment
# ---------------------------------------------------------------------------


def test_geographies_differ_in_churn_and_engagement(result: GenerationResult) -> None:
    """The brief calls out "patterns evolving across geographies"."""
    summary = geo_summary(result)
    assert len(summary) == 6

    assert summary["monthly_churn_rate"].nunique() > 1
    assert summary["avg_coding_hours"].nunique() > 1
    # The spread must be visible, not float noise.
    spread = summary["monthly_churn_rate"].max() - summary["monthly_churn_rate"].min()
    assert spread > 0.002, f"geo churn spread is only {spread:.5f}"


def test_geo_engagement_ordering_follows_configuration(result: GenerationResult) -> None:
    """APAC is configured with the highest coding-hours multiplier; MEA the lowest."""
    from datagen.reference import GEOS

    summary = geo_summary(result)
    configured_top = max(GEOS, key=lambda g: g.hours_mult).code
    configured_bottom = min(GEOS, key=lambda g: g.hours_mult).code

    assert (
        summary.loc[configured_top, "avg_coding_hours"]
        > summary.loc[configured_bottom, "avg_coding_hours"]
    )


def test_power_user_segment_is_a_plausible_minority(result: GenerationResult) -> None:
    """A segment that is everyone (or no one) is useless for targeting."""
    share = result.frames["users"]["power_user_flag"].mean()
    assert 0.05 < share < 0.40, f"power-user share is {share:.3f}"


def test_power_user_flag_is_recomputable_from_usage_events(
    result: GenerationResult,
) -> None:
    """Recompute the **sustained** rule from `usage_events` and demand equality.

    Not merely "every flagged user qualified once" — that weaker check would pass
    even if the flag were the looser ever-qualified rule. This reproduces the
    documented rule exactly (a qualifying week needs >= `power_user_hours` on
    >= `power_user_days` days; a qualifying month contains such a week; the flag
    needs qualifying months to be >= `POWER_USER_MONTH_SHARE` of active months,
    over >= `POWER_USER_MIN_MONTHS`) and asserts set equality, so the published
    column is fully verifiable from the emitted data.
    """
    import numpy as np

    from datagen.usage import POWER_USER_MIN_MONTHS, POWER_USER_MONTH_SHARE

    config = result.config
    events = result.frames["usage_events"].copy()
    events["month"] = events["event_date"].dt.to_period("M")
    # Monday-anchored weeks, matching the generator's week indexing.
    events["week"] = events["event_date"].dt.to_period("W-SUN")

    active_months = events.groupby("user_id")["month"].nunique()

    qualifying_days = events[events["coding_hours"] >= config.power_user_hours]
    per_week = qualifying_days.groupby(["user_id", "week"]).size()
    good_weeks = per_week[per_week >= config.power_user_days].reset_index()

    if good_weeks.empty:
        qualifying_months = active_months * 0
    else:
        # Attribute each qualifying week to the month containing its first day,
        # exactly as the generator does.
        good_weeks["month"] = good_weeks["week"].dt.start_time.dt.to_period("M")
        qualifying_months = good_weeks.groupby("user_id")["month"].nunique()

    qualifying_months = qualifying_months.reindex(active_months.index, fill_value=0)
    threshold = np.ceil(POWER_USER_MONTH_SHARE * active_months.clip(lower=1))
    expected = set(
        active_months.index[
            (active_months >= POWER_USER_MIN_MONTHS)
            & (qualifying_months >= threshold)
            & (qualifying_months > 0)
        ]
    )

    users = result.frames["users"]
    flagged = set(users.loc[users["power_user_flag"], "user_id"])

    assert flagged == expected, (
        f"{len(flagged - expected)} flagged users fail the recomputed sustained "
        f"rule; {len(expected - flagged)} users meet it but are not flagged"
    )


def test_power_user_flag_is_stricter_than_ever_qualified(
    result: GenerationResult,
) -> None:
    """The flag must be the sustained rule, not "qualified in any single week".

    Pins the distinction the schema documents: the loose reading flags materially
    more users, so if the implementation ever reverted to it this fails.
    """
    config = result.config
    events = result.frames["usage_events"].copy()
    events["week"] = events["event_date"].dt.to_period("W-SUN")
    qualifying = events[events["coding_hours"] >= config.power_user_hours]
    per_week = qualifying.groupby(["user_id", "week"]).size()
    ever = set(per_week[per_week >= config.power_user_days].index.get_level_values(0))

    users = result.frames["users"]
    flagged = set(users.loc[users["power_user_flag"], "user_id"])

    assert flagged < ever, "flag is not stricter than the ever-qualified rule"


def test_reactivation_rate_is_near_the_configured_target(result: GenerationResult) -> None:
    """The CRM reactivation KPI is a knob too, per the brief's +22% story."""
    rate = result.reactivation_rate()
    target = result.config.reactivation_rate
    assert rate == pytest.approx(target, abs=0.03), f"rate={rate:.4f} target={target:.4f}"


def test_retention_touches_causally_reduce_churn(result: GenerationResult) -> None:
    """Turning the retention effect off must raise churn, holding all else fixed.

    This is measured as a counterfactual re-run of the simulation at a *fixed*
    intercept rather than by comparing touched against untouched users in the
    emitted data, for two reasons:

    * **Targeting confounds the observational comparison.** Retention touches are
      aimed at declining users, so touched user-months are higher-risk to begin
      with and can show *more* churn than untouched ones even though the touch
      helped each user it reached.
    * **Calibration would hide it end-to-end.** ``generate()`` re-bisects the
      hazard intercept to hit the configured churn target, so disabling the touch
      effect and regenerating yields the same headline rate by construction.

    Comparing two ``_run`` calls that share draws and intercept isolates the
    causal effect of the touch itself.
    """
    import datagen.lifecycle as lifecycle_module
    from datagen.lifecycle import _build_draws, _run, build_features

    population = result.population
    features = build_features(population)
    draws = _build_draws(result.config)
    intercept = result.lifecycle.intercept

    def churn_rate(run: dict) -> float:
        return float(run["churned"].sum()) / float(run["at_risk"].sum())

    with_touch = churn_rate(_run(population, features, draws, intercept))

    original = lifecycle_module.BETA_RETENTION_TOUCH
    try:
        lifecycle_module.BETA_RETENTION_TOUCH = 0.0
        without_touch = churn_rate(_run(population, features, draws, intercept))
    finally:
        lifecycle_module.BETA_RETENTION_TOUCH = original

    assert with_touch < without_touch, (
        f"retention touches did not reduce churn: with={with_touch:.5f} "
        f"without={without_touch:.5f}"
    )


def test_retention_touches_target_declining_users(result: GenerationResult) -> None:
    """The CRM motion must aim at at-risk users — that is the program's premise."""
    touches = result.frames["crm_touches"]
    campaigns = result.frames["crm_campaigns"]
    retention_ids = set(campaigns.loc[campaigns["objective"] == "retention", "campaign_id"])
    retention = touches[touches["campaign_id"].isin(retention_ids)]

    assert not retention.empty
    assert (retention["user_state_at_touch"] == "at_risk").all()
