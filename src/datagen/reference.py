"""Reference (dimension) data: geographies, personas, plans, features, campaigns.

These are the hand-authored knobs behind the "realism levers" in the project
brief. All of it is invented for the demo — no figure here comes from a real
company.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Geographies — 6 regions, per the brief ("patterns evolving across geographies")
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Geo:
    """One region and how developer behaviour differs there.

    Multipliers are applied to a user's *baseline* engagement; ``churn_logit``
    shifts the monthly churn hazard, so regions differ in both behaviour and
    retention rather than only in row counts.
    """

    code: str
    name: str
    share: float
    countries: tuple[str, ...]
    hours_mult: float
    acceptance_offset: float
    sessions_mult: float
    churn_logit: float
    support_mult: float


GEOS: tuple[Geo, ...] = (
    Geo(
        code="NA",
        name="North America",
        share=0.38,
        countries=("US", "CA", "MX"),
        hours_mult=1.00,
        acceptance_offset=0.000,
        sessions_mult=1.00,
        churn_logit=0.00,
        support_mult=1.00,
    ),
    Geo(
        code="EMEA",
        name="Europe, Middle East (Europe cluster)",
        share=0.26,
        countries=("GB", "DE", "FR", "NL", "SE", "PL", "ES"),
        hours_mult=0.94,
        acceptance_offset=-0.012,
        sessions_mult=0.97,
        churn_logit=-0.10,
        support_mult=0.95,
    ),
    Geo(
        code="APAC",
        name="Asia Pacific",
        share=0.21,
        countries=("IN", "JP", "SG", "KR", "VN", "ID"),
        hours_mult=1.08,
        acceptance_offset=0.020,
        sessions_mult=1.06,
        churn_logit=0.18,
        support_mult=1.15,
    ),
    Geo(
        code="LATAM",
        name="Latin America",
        share=0.07,
        countries=("BR", "AR", "CL", "CO"),
        hours_mult=0.90,
        acceptance_offset=-0.020,
        sessions_mult=0.93,
        churn_logit=0.30,
        support_mult=1.10,
    ),
    Geo(
        code="MEA",
        name="Middle East & Africa",
        share=0.04,
        countries=("AE", "SA", "ZA", "NG", "EG"),
        hours_mult=0.86,
        acceptance_offset=-0.028,
        sessions_mult=0.90,
        churn_logit=0.36,
        support_mult=1.20,
    ),
    Geo(
        code="ANZ",
        name="Australia & New Zealand",
        share=0.04,
        countries=("AU", "NZ"),
        hours_mult=0.96,
        acceptance_offset=0.004,
        sessions_mult=0.98,
        churn_logit=-0.06,
        support_mult=0.92,
    ),
)

GEO_BY_CODE: dict[str, Geo] = {g.code: g for g in GEOS}
GEO_CODES: tuple[str, ...] = tuple(g.code for g in GEOS)
GEO_SHARES: dict[str, float] = {g.code: g.share for g in GEOS}


# ---------------------------------------------------------------------------
# Latent engagement archetypes.
#
# NOTE: the archetype is a *generator-internal* latent variable and is
# deliberately NOT emitted in the `users` table — publishing it would leak the
# churn label into the feature set and make the downstream ML stage trivial.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Archetype:
    """A behavioural cohort: where engagement starts and which way it drifts."""

    name: str
    share: float
    hours_median: float
    hours_sigma: float
    acceptance_mean: float
    sessions_median: float
    active_day_prob: float
    #: Mean monthly log-drift of the engagement index (negative = declining).
    drift_mean: float
    drift_sigma: float


ARCHETYPES: tuple[Archetype, ...] = (
    Archetype(
        name="power",
        share=0.18,
        hours_median=5.6,
        hours_sigma=0.26,
        acceptance_mean=0.46,
        sessions_median=6.2,
        active_day_prob=0.93,
        drift_mean=0.006,
        drift_sigma=0.030,
    ),
    Archetype(
        name="steady",
        share=0.42,
        hours_median=3.4,
        hours_sigma=0.34,
        acceptance_mean=0.36,
        sessions_median=3.9,
        active_day_prob=0.78,
        drift_mean=-0.002,
        drift_sigma=0.042,
    ),
    Archetype(
        name="casual",
        share=0.28,
        hours_median=1.7,
        hours_sigma=0.44,
        acceptance_mean=0.29,
        sessions_median=2.1,
        active_day_prob=0.52,
        drift_mean=-0.014,
        drift_sigma=0.055,
    ),
    Archetype(
        name="fading",
        share=0.12,
        hours_median=2.3,
        hours_sigma=0.48,
        acceptance_mean=0.25,
        sessions_median=2.4,
        active_day_prob=0.58,
        drift_mean=-0.085,
        drift_sigma=0.060,
    ),
)

ARCHETYPE_SHARES: dict[str, float] = {a.name: a.share for a in ARCHETYPES}
ARCHETYPE_BY_NAME: dict[str, Archetype] = {a.name: a for a in ARCHETYPES}


# ---------------------------------------------------------------------------
# Value-add descriptive attributes (persona / entitlements / acquisition).
# These are enrichment dimensions, not churn labels.
# ---------------------------------------------------------------------------

PERSONAS: dict[str, float] = {
    "individual_dev": 0.44,
    "team_lead": 0.19,
    "startup_founder": 0.12,
    "freelancer": 0.14,
    "student": 0.11,
}

COMPANY_SIZE_BUCKETS: dict[str, float] = {
    "1": 0.28,
    "2-10": 0.24,
    "11-50": 0.20,
    "51-200": 0.15,
    "201-1000": 0.09,
    "1000+": 0.04,
}

ACQUISITION_CHANNELS: dict[str, float] = {
    "organic_search": 0.27,
    "word_of_mouth": 0.24,
    "social": 0.16,
    "paid_search": 0.13,
    "developer_conference": 0.08,
    "partner_marketplace": 0.07,
    "content_marketing": 0.05,
}


# ---------------------------------------------------------------------------
# Plans / billing (asset A03)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    """A purchasable plan. Prices are the round demo price points from the brief."""

    plan_id: str
    plan_name: str
    tier: str
    billing_period: str
    list_price_usd: float
    mrr_usd: float
    share: float


PLANS: tuple[Plan, ...] = (
    Plan("pro_monthly", "Pro Monthly", "pro", "monthly", 20.0, 20.0, 0.68),
    Plan("pro_annual", "Pro Annual", "pro", "annual", 192.0, 16.0, 0.24),
    Plan("pro_team_monthly", "Pro Team Monthly", "pro", "monthly", 40.0, 40.0, 0.08),
)

PLAN_BY_ID: dict[str, Plan] = {p.plan_id: p for p in PLANS}

#: Where a downgrade lands. Pro Team -> Pro, annual -> monthly.
DOWNGRADE_TARGET: dict[str, str] = {
    "pro_team_monthly": "pro_monthly",
    "pro_annual": "pro_monthly",
    "pro_monthly": "pro_monthly",
}

CANCEL_REASONS: dict[str, float] = {
    "stopped_using": 0.31,
    "too_expensive": 0.22,
    "switched_competitor": 0.16,
    "missing_features": 0.12,
    "quality_of_suggestions": 0.10,
    "employer_provided_license": 0.06,
    "other": 0.03,
}


# ---------------------------------------------------------------------------
# Stickiness features (asset A07)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Feature:
    """A product feature whose adoption is a stickiness signal.

    ``stickiness`` is how strongly adoption suppresses the churn hazard;
    ``base_adoption`` is the propensity to ever adopt it at baseline engagement.
    """

    feature_key: str
    feature_name: str
    feature_family: str
    base_adoption: float
    stickiness: float
    activations_per_active_day: float


FEATURES: tuple[Feature, ...] = (
    Feature("tab_completion", "Inline Tab Completion", "core_ai", 0.94, 0.10, 24.0),
    Feature("codebase_chat", "Codebase-Aware Chat", "core_ai", 0.71, 0.22, 6.0),
    Feature("agent_mode", "Agentic Multi-Step Edits", "agentic", 0.42, 0.34, 2.4),
    Feature("multi_file_edit", "Multi-File Edit", "agentic", 0.38, 0.28, 1.8),
    Feature("terminal_ai", "AI Terminal Commands", "productivity", 0.33, 0.16, 3.1),
    Feature("project_rules", "Project Rules Files", "customization", 0.21, 0.30, 0.6),
)

FEATURE_BY_KEY: dict[str, Feature] = {f.feature_key: f for f in FEATURES}


# ---------------------------------------------------------------------------
# Support (asset A14)
# ---------------------------------------------------------------------------

SUPPORT_CHANNELS: dict[str, float] = {
    "in_app_chat": 0.46,
    "email": 0.34,
    "community_forum": 0.13,
    "phone": 0.07,
}

SUPPORT_CATEGORIES: dict[str, float] = {
    "suggestion_quality": 0.24,
    "performance_latency": 0.19,
    "billing": 0.16,
    "indexing_failure": 0.14,
    "account_login": 0.11,
    "feature_request": 0.10,
    "integration": 0.06,
}

SUPPORT_PRIORITIES: dict[str, float] = {
    "P3_low": 0.44,
    "P2_normal": 0.38,
    "P1_high": 0.14,
    "P0_urgent": 0.04,
}


# ---------------------------------------------------------------------------
# CRM campaigns — 5 campaigns (brief: ~4-6), each with a channel and an
# objective. Retention plays target at-risk actives; winback targets lapsed.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Campaign:
    """A CRM campaign definition.

    Args:
        objective: ``retention`` (at-risk actives), ``winback`` (lapsed users),
            ``adoption`` (stickiness nudge) or ``expansion`` (upsell).
        reach: Share of the eligible segment touched in a given month.
        lift: How effective this campaign is relative to the program baseline.
            Its meaning depends on ``objective``: for ``winback`` it multiplies
            the configured reactivation rate; for ``retention`` it scales the
            campaign's churn-hazard reduction. ``adoption`` and ``expansion``
            campaigns are modelled as touches with outcomes but no direct churn
            effect, so ``lift`` is descriptive only for them.
        month_offset / duration_months: When the campaign is live, expressed in
            months from the start of the observation window.
    """

    campaign_id: str
    campaign_name: str
    objective: str
    channel: str
    target_segment: str
    offer_type: str
    budget_usd: float
    reach: float
    lift: float
    month_offset: int
    duration_months: int


CAMPAIGNS: tuple[Campaign, ...] = (
    Campaign(
        campaign_id="CMP-001",
        campaign_name="At-Risk Behavioral Nudge",
        objective="retention",
        channel="email",
        target_segment="declining_engagement_active",
        offer_type="usage_tips_digest",
        budget_usd=180_000.0,
        reach=0.62,
        lift=1.00,
        month_offset=0,
        duration_months=18,
    ),
    Campaign(
        campaign_id="CMP-002",
        campaign_name="Power User Retention Concierge",
        objective="retention",
        channel="in_app",
        target_segment="declining_engagement_power_user",
        offer_type="dedicated_success_session",
        budget_usd=240_000.0,
        reach=0.48,
        lift=1.45,
        month_offset=2,
        duration_months=16,
    ),
    Campaign(
        campaign_id="CMP-003",
        campaign_name="Lapsed Pro Winback",
        objective="winback",
        channel="email",
        target_segment="lapsed_within_90d",
        offer_type="two_months_50pct_off",
        budget_usd=210_000.0,
        reach=0.71,
        # The sole winback campaign, so its lift is 1.0: the realised
        # reactivation rate then lands on the configured target directly, which
        # is what the KPI table in the evidence compares against.
        lift=1.00,
        month_offset=1,
        duration_months=17,
    ),
    Campaign(
        campaign_id="CMP-004",
        campaign_name="Agent Mode Adoption Series",
        objective="adoption",
        channel="in_app",
        target_segment="low_feature_adoption_active",
        offer_type="guided_walkthrough",
        budget_usd=120_000.0,
        reach=0.55,
        lift=1.12,
        month_offset=4,
        duration_months=14,
    ),
    Campaign(
        campaign_id="CMP-005",
        campaign_name="Annual Plan Upgrade Offer",
        objective="expansion",
        channel="push",
        target_segment="engaged_monthly_billers",
        offer_type="annual_switch_2_months_free",
        budget_usd=95_000.0,
        reach=0.30,
        lift=0.88,
        month_offset=6,
        duration_months=12,
    ),
)

CAMPAIGN_BY_ID: dict[str, Campaign] = {c.campaign_id: c for c in CAMPAIGNS}

MESSAGE_VARIANTS: tuple[str, ...] = ("A_control", "B_personalized", "C_incentive")

TOUCH_OUTCOMES: tuple[str, ...] = (
    "reactivated",
    "engaged_no_conversion",
    "no_response",
    "unsubscribed",
)
