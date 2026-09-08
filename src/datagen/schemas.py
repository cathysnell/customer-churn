"""Table schemas — the single source of truth for the data dictionary.

Each :class:`TableSpec` declares its columns, dtypes, grain, keys and the data
asset it corresponds to in the project brief (A03/A06/A07/A14). Three things
consume this module:

1. :mod:`datagen.pipeline` validates and column-orders every emitted frame
   against it, so a schema drift fails the run instead of the downstream stage.
2. :mod:`datagen.evidence` renders the human-readable data dictionary.
3. :mod:`datagen.writer` renders the Unity Catalog DDL / registration intent.

The ``sql_type`` values are Databricks SQL types, so the DDL this generates is
directly usable by the Unity Catalog stage.
"""

from __future__ import annotations

from dataclasses import dataclass

# Pandas dtype -> Databricks SQL type. Kept explicit rather than inferred so the
# DDL handed to the UC stage is stable across pandas versions.
_SQL_TYPES: dict[str, str] = {
    "string": "STRING",
    "int64": "BIGINT",
    "int32": "INT",
    "int16": "SMALLINT",
    "float64": "DOUBLE",
    "bool": "BOOLEAN",
    "datetime64[ns]": "TIMESTAMP",
    "date": "DATE",
}


@dataclass(frozen=True)
class ColumnSpec:
    """One column: name, pandas dtype, and what it means."""

    name: str
    dtype: str
    description: str
    nullable: bool = False

    @property
    def sql_type(self) -> str:
        return _SQL_TYPES[self.dtype]

    @property
    def pandas_dtype(self) -> str:
        """The dtype to actually cast to (``date`` is stored as datetime64)."""
        return "datetime64[ns]" if self.dtype == "date" else self.dtype


@dataclass(frozen=True)
class TableSpec:
    """One output table."""

    name: str
    asset: str
    layer: str
    grain: str
    description: str
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...]
    foreign_keys: tuple[tuple[str, str], ...] = ()
    partition_by: tuple[str, ...] = ()

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def column(self, name: str) -> ColumnSpec:
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(f"{self.name} has no column {name!r}")

    def dtype_map(self) -> dict[str, str]:
        return {c.name: c.pandas_dtype for c in self.columns}


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

USERS = TableSpec(
    name="users",
    asset="VA (identity / persona / entitlements)",
    layer="bronze",
    grain="one row per Pro-tier user",
    description=(
        "The Pro-tier user dimension: signup, geography, persona and the "
        "power-user flag derived from observed daily engagement."
    ),
    columns=(
        ColumnSpec("user_id", "string", "Synthetic surrogate user key, `USR-########`."),
        ColumnSpec("signup_date", "date", "Date the user first became a Pro subscriber."),
        ColumnSpec("geo", "string", "Region code: NA, EMEA, APAC, LATAM, MEA, ANZ."),
        ColumnSpec("country", "string", "ISO-3166 alpha-2 country within the region."),
        ColumnSpec("plan", "string", "Plan at signup (see `subscriptions.plan_id`)."),
        ColumnSpec("tier", "string", "Subscription tier; always `pro` in this dataset."),
        ColumnSpec("persona", "string", "Value-add persona label for CRM targeting."),
        ColumnSpec("company_size", "string", "Self-reported company-size bucket."),
        ColumnSpec("acquisition_channel", "string", "How the user was acquired."),
        ColumnSpec("primary_language", "string", "Most-used programming language."),
        ColumnSpec("ide_theme", "string", "Cosmetic preference; a deliberate non-signal."),
        ColumnSpec(
            "power_user_flag",
            "bool",
            "TRUE for SUSTAINED power users. A week qualifies when the user hit "
            ">=4 coding hours/day on >=5 days; a month qualifies when it contains "
            "a qualifying week. The flag is TRUE when qualifying months are at "
            "least half of the months the user was active, over >=2 active "
            "months. Note this is stricter than 'ever qualified once' (which "
            "would flag ~37% of an 18-month population, including now-dormant "
            "users). Recomputable from usage_events.",
        ),
        ColumnSpec(
            "tenure_days_at_window_end",
            "int64",
            "Days from signup to the end of the observation window.",
        ),
    ),
    primary_key=("user_id",),
    partition_by=("geo",),
)


# ---------------------------------------------------------------------------
# subscriptions (A03)
# ---------------------------------------------------------------------------

SUBSCRIPTIONS = TableSpec(
    name="subscriptions",
    asset="A03 — subscription plans & billing history",
    layer="bronze",
    grain="one row per subscription term (a plan a user held for a period)",
    description=(
        "Subscription lifecycle and billing history: signup, renewals, "
        "downgrades and cancellation, with recognised revenue per term."
    ),
    columns=(
        ColumnSpec("subscription_id", "string", "Surrogate key, `SUB-#########`."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("plan_id", "string", "Plan held during this term."),
        ColumnSpec("plan_name", "string", "Human-readable plan name."),
        ColumnSpec("tier", "string", "Tier of the plan held (`pro`)."),
        ColumnSpec("billing_period", "string", "`monthly` or `annual`."),
        ColumnSpec("mrr_usd", "float64", "Monthly recurring revenue for this term."),
        ColumnSpec("list_price_usd", "float64", "Sticker price per billing period."),
        ColumnSpec("term_start_date", "date", "First day the user held this plan."),
        ColumnSpec(
            "term_end_date",
            "date",
            "Last day of the term; NULL while the term is still open.",
            nullable=True,
        ),
        ColumnSpec("term_index", "int64", "0-based sequence of terms for the user."),
        ColumnSpec(
            "status",
            "string",
            "`active`, `downgraded`, `canceled`, or `churned_after_reactivation`.",
        ),
        ColumnSpec("renewals_count", "int64", "Successful renewals billed in this term."),
        ColumnSpec("payment_failures", "int64", "Failed payment attempts in this term."),
        ColumnSpec("is_downgrade", "bool", "TRUE if this term began as a downgrade."),
        ColumnSpec("is_reactivation", "bool", "TRUE if this term began as a winback."),
        ColumnSpec(
            "cancel_date",
            "date",
            "Date the subscription was canceled; NULL if not canceled.",
            nullable=True,
        ),
        ColumnSpec(
            "cancel_reason",
            "string",
            "Reason code for cancellation; NULL if not canceled.",
            nullable=True,
        ),
        ColumnSpec("revenue_usd", "float64", "Revenue recognised over the term."),
    ),
    primary_key=("subscription_id",),
    foreign_keys=(("user_id", "users.user_id"),),
    partition_by=(),
)


# ---------------------------------------------------------------------------
# usage_events (A06) — the streaming behavioural signal
# ---------------------------------------------------------------------------

USAGE_EVENTS = TableSpec(
    name="usage_events",
    asset="A06 — raw product usage events & telemetry",
    layer="bronze",
    grain="one row per user per ACTIVE day (inactive days are not emitted)",
    description=(
        "The daily behavioural signal and the Structured Streaming / Lakeflow "
        "ingest source: active coding hours, AI-suggestion acceptance rate and "
        "session frequency. Only active days are emitted, so row count is well "
        "below users x days."
    ),
    columns=(
        ColumnSpec("event_date", "date", "Activity date (partition column)."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("geo", "string", "Denormalised region code for partition pruning."),
        ColumnSpec(
            "coding_hours",
            "float64",
            "Active coding hours that day (editor-focused time), 0.05-16.",
        ),
        ColumnSpec(
            "ai_suggestion_acceptance_rate",
            "float64",
            "Accepted AI suggestions / suggestions shown that day, 0-1.",
        ),
        ColumnSpec(
            "session_frequency",
            "int64",
            "Distinct editor sessions started that day.",
        ),
        ColumnSpec("suggestions_shown", "int64", "AI suggestions surfaced that day."),
        ColumnSpec("suggestions_accepted", "int64", "AI suggestions accepted that day."),
        ColumnSpec("lines_of_code_written", "int64", "Net lines written that day."),
        ColumnSpec("files_touched", "int64", "Distinct files edited that day."),
        ColumnSpec("ai_requests", "int64", "Chat / agent requests issued that day."),
        ColumnSpec("is_weekend", "bool", "TRUE for Saturday/Sunday activity."),
    ),
    primary_key=("user_id", "event_date"),
    foreign_keys=(("user_id", "users.user_id"),),
    partition_by=("event_date",),
)


# ---------------------------------------------------------------------------
# feature_adoption (A07)
# ---------------------------------------------------------------------------

FEATURE_ADOPTION = TableSpec(
    name="feature_adoption",
    asset="A07 — feature adoption & activation metrics",
    layer="bronze",
    grain="one row per user per feature per month",
    description=(
        "Monthly adoption and activation intensity for the stickiness features. "
        "Adoption suppresses churn hazard, so this is a first-class model input."
    ),
    columns=(
        ColumnSpec("month_start", "date", "First day of the calendar month."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("feature_key", "string", "Stable feature identifier."),
        ColumnSpec("feature_name", "string", "Human-readable feature name."),
        ColumnSpec("feature_family", "string", "Feature grouping for rollups."),
        ColumnSpec("is_adopted", "bool", "TRUE if the user had activated it by then."),
        ColumnSpec(
            "first_activation_date",
            "date",
            "Date of first activation; NULL if never adopted.",
            nullable=True,
        ),
        ColumnSpec("activation_count", "int64", "Times the feature was used that month."),
        ColumnSpec("active_days", "int64", "Days that month the feature was used."),
        ColumnSpec(
            "depth_score",
            "float64",
            "0-1 usage depth: how heavily the feature was used when available.",
        ),
    ),
    primary_key=("user_id", "feature_key", "month_start"),
    foreign_keys=(("user_id", "users.user_id"),),
    partition_by=("month_start",),
)


# ---------------------------------------------------------------------------
# support_tickets (A14)
# ---------------------------------------------------------------------------

SUPPORT_TICKETS = TableSpec(
    name="support_tickets",
    asset="A14 — support tickets, chat logs & CSAT",
    layer="bronze",
    grain="one row per support ticket",
    description=(
        "Support friction as a churn signal: ticket volume, chat message "
        "volume, handling time and CSAT. Volume rises as engagement declines."
    ),
    columns=(
        ColumnSpec("ticket_id", "string", "Surrogate key, `TCK-#########`."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("created_date", "date", "Date the ticket was opened."),
        ColumnSpec("channel", "string", "Contact channel used."),
        ColumnSpec("category", "string", "Issue category."),
        ColumnSpec("priority", "string", "Triaged priority, `P0_urgent`..`P3_low`."),
        ColumnSpec("chat_message_count", "int64", "Messages exchanged on the ticket."),
        ColumnSpec("first_response_minutes", "int64", "Minutes to first agent reply."),
        ColumnSpec("resolution_hours", "float64", "Hours from open to resolution."),
        ColumnSpec("reopened_count", "int64", "Times the ticket was reopened."),
        ColumnSpec("is_escalated", "bool", "TRUE if escalated beyond tier-1 support."),
        ColumnSpec(
            "csat_score",
            "float64",
            "1-5 satisfaction score; NULL when the user did not respond.",
            nullable=True,
        ),
        ColumnSpec("resolved", "bool", "TRUE if the ticket reached a resolved state."),
    ),
    primary_key=("ticket_id",),
    foreign_keys=(("user_id", "users.user_id"),),
    partition_by=(),
)


# ---------------------------------------------------------------------------
# crm_campaigns / crm_touches
# ---------------------------------------------------------------------------

CRM_CAMPAIGNS = TableSpec(
    name="crm_campaigns",
    asset="VA (marketing saturation / campaign metadata)",
    layer="bronze",
    grain="one row per CRM campaign",
    description="Campaign dimension: objective, channel, target segment, budget, run dates.",
    columns=(
        ColumnSpec("campaign_id", "string", "Campaign key, `CMP-###`."),
        ColumnSpec("campaign_name", "string", "Human-readable campaign name."),
        ColumnSpec(
            "objective",
            "string",
            "`retention`, `winback`, `adoption` or `expansion`.",
        ),
        ColumnSpec("channel", "string", "`email`, `in_app` or `push`."),
        ColumnSpec("target_segment", "string", "Rule describing who is eligible."),
        ColumnSpec("offer_type", "string", "What the touch offers the user."),
        ColumnSpec("budget_usd", "float64", "Planned campaign budget."),
        ColumnSpec("start_date", "date", "First day the campaign was live."),
        ColumnSpec("end_date", "date", "Last day the campaign was live."),
        ColumnSpec("is_active_at_window_end", "bool", "TRUE if still live on the last day."),
    ),
    primary_key=("campaign_id",),
    partition_by=(),
)


CRM_TOUCHES = TableSpec(
    name="crm_touches",
    asset="VA (CRM touch + reactivation outcome)",
    layer="bronze",
    grain="one row per campaign touch sent to a user",
    description=(
        "Individual campaign sends and their outcome. `outcome = 'reactivated'` "
        "is the numerator of the CRM reactivation-rate KPI."
    ),
    columns=(
        ColumnSpec("touch_id", "string", "Surrogate key, `TCH-##########`."),
        ColumnSpec("campaign_id", "string", "FK to `crm_campaigns.campaign_id`."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("touch_date", "date", "Date the touch was sent."),
        ColumnSpec("channel", "string", "Channel the touch went out on."),
        ColumnSpec("message_variant", "string", "A/B/C message variant."),
        ColumnSpec("delivered", "bool", "TRUE if the touch was delivered."),
        ColumnSpec("opened", "bool", "TRUE if the user opened it."),
        ColumnSpec("clicked", "bool", "TRUE if the user clicked through."),
        ColumnSpec(
            "outcome",
            "string",
            "`reactivated`, `engaged_no_conversion`, `no_response` or `unsubscribed`.",
        ),
        ColumnSpec("reactivated", "bool", "Convenience flag: outcome == 'reactivated'."),
        ColumnSpec(
            "user_state_at_touch",
            "string",
            "`active`, `at_risk` or `lapsed` when the touch was sent.",
        ),
        ColumnSpec("cost_usd", "float64", "Marginal cost of the touch."),
    ),
    primary_key=("touch_id",),
    foreign_keys=(
        ("user_id", "users.user_id"),
        ("campaign_id", "crm_campaigns.campaign_id"),
    ),
    partition_by=("touch_date",),
)


# ---------------------------------------------------------------------------
# churn_labels — the supervised training target
# ---------------------------------------------------------------------------

CHURN_LABELS = TableSpec(
    name="churn_labels",
    asset="derived label (gold) — supervised training target",
    layer="gold",
    grain="one row per user per month the user was a subscriber at month start",
    description=(
        "Per-user monthly churn label. `churned = TRUE` means the user was an "
        "active subscriber on the first day of the month and canceled during "
        "it. Rows only exist for months the user was at risk, so "
        "AVG(churned) is the monthly churn rate directly."
    ),
    columns=(
        ColumnSpec("month_start", "date", "First day of the observation month."),
        ColumnSpec("user_id", "string", "FK to `users.user_id`."),
        ColumnSpec("geo", "string", "Denormalised region code."),
        ColumnSpec(
            "churned",
            "bool",
            "THE LABEL: TRUE if the user canceled during this month.",
        ),
        ColumnSpec(
            "churn_date",
            "date",
            "Cancellation date when churned; NULL otherwise.",
            nullable=True,
        ),
        ColumnSpec("tenure_months", "int64", "Whole months from signup to month start."),
        ColumnSpec("is_power_user_month", "bool", "TRUE if the power-user bar was met."),
        ColumnSpec("active_days", "int64", "Active days observed that month."),
        ColumnSpec("avg_coding_hours", "float64", "Mean coding hours over active days."),
        ColumnSpec("avg_acceptance_rate", "float64", "Mean AI-acceptance over active days."),
        ColumnSpec("avg_session_frequency", "float64", "Mean sessions/day over active days."),
        ColumnSpec(
            "coding_hours_trend_30d",
            "float64",
            "Ratio of this month's mean coding hours to the prior month's "
            "(1.0 = flat, <1 = declining). The headline decline feature.",
        ),
        ColumnSpec("support_tickets_30d", "int64", "Tickets opened during the month."),
        ColumnSpec("features_adopted", "int64", "Distinct stickiness features adopted."),
        ColumnSpec("crm_touches_30d", "int64", "CRM touches received during the month."),
    ),
    primary_key=("user_id", "month_start"),
    foreign_keys=(("user_id", "users.user_id"),),
    partition_by=("month_start",),
)


TABLES: tuple[TableSpec, ...] = (
    USERS,
    SUBSCRIPTIONS,
    USAGE_EVENTS,
    FEATURE_ADOPTION,
    SUPPORT_TICKETS,
    CRM_CAMPAIGNS,
    CRM_TOUCHES,
    CHURN_LABELS,
)

TABLE_BY_NAME: dict[str, TableSpec] = {t.name: t for t in TABLES}


def table_names() -> tuple[str, ...]:
    """Names of every table the generator emits, in dependency order."""
    return tuple(t.name for t in TABLES)


def spec(name: str) -> TableSpec:
    """Look up a :class:`TableSpec` by table name."""
    try:
        return TABLE_BY_NAME[name]
    except KeyError:
        raise KeyError(f"unknown table {name!r}; known: {table_names()}") from None
