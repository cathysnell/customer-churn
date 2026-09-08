"""Referential integrity and cross-table temporal consistency."""

from __future__ import annotations

import pytest

from datagen import schemas
from datagen.config import GeneratorConfig
from datagen.pipeline import GenerationResult

CHILD_TABLES = [
    "subscriptions",
    "usage_events",
    "feature_adoption",
    "support_tickets",
    "crm_touches",
    "churn_labels",
]


@pytest.mark.parametrize("child", CHILD_TABLES)
def test_every_child_user_id_exists_in_users(child: str, frames: dict) -> None:
    """The headline check: no orphan ``user_id`` anywhere."""
    users = set(frames["users"]["user_id"])
    orphans = set(frames[child]["user_id"]) - users
    assert not orphans, f"{child} has {len(orphans)} user_ids missing from users"


def test_usage_events_user_ids_all_exist(frames: dict) -> None:
    """Stated explicitly because it is the acceptance criterion in the brief."""
    users = set(frames["users"]["user_id"])
    event_users = set(frames["usage_events"]["user_id"])
    assert event_users <= users
    assert event_users, "usage_events has no users at all"


def test_touches_reference_real_campaigns(frames: dict) -> None:
    campaigns = set(frames["crm_campaigns"]["campaign_id"])
    assert set(frames["crm_touches"]["campaign_id"]) <= campaigns


def test_feature_adoption_references_known_features(frames: dict) -> None:
    from datagen.reference import FEATURES

    known = {f.feature_key for f in FEATURES}
    assert set(frames["feature_adoption"]["feature_key"]) <= known


def test_every_user_has_at_least_one_subscription(frames: dict) -> None:
    """A Pro user with no subscription term would break the A03 billing story."""
    users = set(frames["users"]["user_id"])
    with_subs = set(frames["subscriptions"]["user_id"])
    assert users == with_subs


def test_usage_events_fall_inside_the_window(
    frames: dict, small_config: GeneratorConfig
) -> None:
    events = frames["usage_events"]
    assert events["event_date"].min() >= small_config.window_start
    assert events["event_date"].max() <= small_config.window_end


def test_usage_events_never_precede_signup(frames: dict) -> None:
    """A user cannot generate activity before they existed."""
    merged = frames["usage_events"].merge(
        frames["users"][["user_id", "signup_date"]], on="user_id", how="left"
    )
    early = merged[merged["event_date"] < merged["signup_date"]]
    assert early.empty, f"{len(early)} usage rows precede the user's signup_date"


def test_no_usage_events_during_a_lapse(frames: dict) -> None:
    """After cancelling, a user emits no activity unless they were won back."""
    subs = frames["subscriptions"]
    canceled = subs[subs["cancel_date"].notna()]
    reactivated = set(subs.loc[subs["is_reactivation"], "user_id"])

    last_cancel = (
        canceled[~canceled["user_id"].isin(reactivated)]
        .groupby("user_id", as_index=False)["cancel_date"]
        .max()
    )
    merged = frames["usage_events"].merge(last_cancel, on="user_id", how="inner")
    leaked = merged[merged["event_date"] > merged["cancel_date"]]
    assert leaked.empty, f"{len(leaked)} usage rows occur after cancellation"


def test_churn_labels_only_cover_at_risk_months(result: GenerationResult) -> None:
    """One label row per user-month at risk — that is what makes AVG() the rate."""
    labels = result.frames["churn_labels"]
    assert len(labels) == int(result.lifecycle.at_risk.sum())


def test_churn_date_present_exactly_when_churned(frames: dict) -> None:
    labels = frames["churn_labels"]
    assert labels.loc[labels["churned"], "churn_date"].notna().all()
    assert labels.loc[~labels["churned"], "churn_date"].isna().all()


def test_churn_date_falls_inside_its_label_month(frames: dict) -> None:
    """A churn recorded in March must have happened in March."""
    churned = frames["churn_labels"]
    churned = churned[churned["churned"]]
    same_month = churned["churn_date"].dt.to_period("M") == churned[
        "month_start"
    ].dt.to_period("M")
    assert same_month.all(), "some churn_date values fall outside their label month"


def test_cancel_reason_present_exactly_when_canceled(frames: dict) -> None:
    subs = frames["subscriptions"]
    assert subs.loc[subs["cancel_date"].notna(), "cancel_reason"].notna().all()
    assert subs.loc[subs["cancel_date"].isna(), "cancel_reason"].isna().all()


def test_subscription_terms_do_not_overlap(frames: dict) -> None:
    """Terms per user are chronological and non-overlapping."""
    subs = frames["subscriptions"].sort_values(["user_id", "term_index"])
    grouped = subs.groupby("user_id")
    for user_id, group in grouped:
        if len(group) < 2:
            continue
        ends = group["term_end_date"].tolist()
        starts = group["term_start_date"].tolist()
        # Every term except the last must be closed.
        assert all(e is not None and e == e for e in ends[:-1]), (
            f"{user_id} has an open term before its last term"
        )
        for previous_end, next_start in zip(ends[:-1], starts[1:], strict=True):
            assert previous_end <= next_start, f"{user_id} has overlapping terms"


def test_only_one_open_term_per_user(frames: dict) -> None:
    subs = frames["subscriptions"]
    open_terms = subs[subs["term_end_date"].isna()]
    assert not open_terms["user_id"].duplicated().any()


def test_reactivated_outcome_only_on_winback_campaigns(frames: dict) -> None:
    """``outcome == 'reactivated'`` must mean a lapsed user resubscribed."""
    touches = frames["crm_touches"]
    campaigns = frames["crm_campaigns"]
    winback = set(campaigns.loc[campaigns["objective"] == "winback", "campaign_id"])

    reactivated = touches[touches["reactivated"]]
    assert set(reactivated["campaign_id"]) <= winback
    assert (reactivated["outcome"] == "reactivated").all()
    assert (reactivated["user_state_at_touch"] == "lapsed").all()


def test_reactivated_users_have_a_reactivation_term(frames: dict) -> None:
    """Every reactivation touch is backed by a real new subscription term."""
    touches = frames["crm_touches"]
    reactivated_users = set(touches.loc[touches["reactivated"], "user_id"])
    subs = frames["subscriptions"]
    term_users = set(subs.loc[subs["is_reactivation"], "user_id"])
    assert reactivated_users == term_users


def test_touch_dates_inside_campaign_run_dates(frames: dict) -> None:
    merged = frames["crm_touches"].merge(
        frames["crm_campaigns"][["campaign_id", "start_date", "end_date"]],
        on="campaign_id",
        how="left",
    )
    assert (merged["touch_date"] >= merged["start_date"]).all()
    assert (merged["touch_date"] <= merged["end_date"]).all()


def test_suggestions_accepted_never_exceeds_shown(frames: dict) -> None:
    events = frames["usage_events"]
    assert (events["suggestions_accepted"] <= events["suggestions_shown"]).all()


def test_acceptance_rate_matches_its_components(frames: dict) -> None:
    """The published rate must equal accepted/shown, not an unrelated draw."""
    events = frames["usage_events"]
    recomputed = events["suggestions_accepted"] / events["suggestions_shown"]
    assert (events["ai_suggestion_acceptance_rate"] - recomputed).abs().max() < 1e-3


def test_feature_active_days_never_exceed_user_active_days(frames: dict) -> None:
    """A feature cannot be used on more days than the user was active."""
    labels = frames["churn_labels"][["user_id", "month_start", "active_days"]]
    merged = frames["feature_adoption"].merge(
        labels, on=["user_id", "month_start"], how="inner", suffixes=("_feature", "_user")
    )
    assert (merged["active_days_feature"] <= merged["active_days_user"]).all()


def test_validate_reports_no_failures(result: GenerationResult) -> None:
    """The same checks the CLI prints into the evidence file must all pass."""
    from datagen.pipeline import validate

    failures = [line for line in validate(result) if "FAIL" in line]
    assert not failures, failures


def test_all_geographies_and_features_are_represented(frames: dict) -> None:
    """The brief asks for ~6 geographies and a set of stickiness features."""
    from datagen.reference import FEATURES, GEO_CODES

    assert set(frames["users"]["geo"]) == set(GEO_CODES)
    assert len(GEO_CODES) == 6
    assert set(frames["feature_adoption"]["feature_key"]) == {f.feature_key for f in FEATURES}


def test_campaign_count_matches_brief(frames: dict) -> None:
    """Brief: ~4-6 CRM campaigns."""
    assert 4 <= len(frames["crm_campaigns"]) <= 6


def test_churn_labels_geo_matches_users(frames: dict) -> None:
    """Denormalised ``geo`` must agree with the user dimension."""
    merged = frames["churn_labels"].merge(
        frames["users"][["user_id", "geo"]], on="user_id", suffixes=("_label", "_user")
    )
    assert (merged["geo_label"] == merged["geo_user"]).all()


def test_every_table_name_is_registered(frames: dict) -> None:
    assert tuple(schemas.table_names()) == tuple(
        spec.name for spec in schemas.TABLES
    )
