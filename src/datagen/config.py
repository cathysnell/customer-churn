"""Volume, time-window and realism knobs for the generator.

Everything that makes a run reproducible lives here. There is **no** use of
wall-clock time anywhere in the generator: the observation window is anchored
to :data:`DEFAULT_END_DATE` so a run today and a run next year produce
byte-identical output for the same seed.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Committed constants. Changing any of these changes the dataset.
# ---------------------------------------------------------------------------

#: The one committed random seed. Documented in the datagen README.
DEFAULT_SEED = 1729

#: Full-scale Pro-tier population (matches the ROI ``Customer_Base`` in the brief).
DEFAULT_USERS = 50_000

#: Months of daily history (brief: 18 months / ~547 days).
DEFAULT_MONTHS = 18

#: Last day of the observation window. Fixed, never ``date.today()``.
DEFAULT_END_DATE = date(2026, 8, 31)

#: Illustrative baseline monthly Pro churn from the brief (4.7%).
DEFAULT_MONTHLY_CHURN_RATE = 0.047

#: Illustrative baseline CRM reactivation rate from the brief (8.0%).
DEFAULT_REACTIVATION_RATE = 0.080

#: Power-user bar from the brief: >= 4 coding hours/day on >= 5 days/week.
POWER_USER_HOURS_PER_DAY = 4.0
POWER_USER_DAYS_PER_WEEK = 5


@dataclass(frozen=True)
class GeneratorConfig:
    """Immutable configuration for one generator run.

    Args:
        users: Number of Pro-tier users to synthesize, *before* ``sample_frac``.
        months: Whole calendar months of daily history.
        sample_frac: Scales ``users`` (the sampling unit is the **user**, not the
            day — see the datagen README for why days are never truncated).
        seed: Master seed. All sub-streams are derived from it.
        end_date: Inclusive last day of the observation window.
        monthly_churn_rate: Target mean monthly churn rate; the churn hazard
            intercept is calibrated to hit this.
        reactivation_rate: Target CRM reactivation rate among targeted users.
        power_user_hours / power_user_days: The power-user daily-engagement bar.
        out_dir: Where :mod:`datagen.writer` lands files.
        output_format: ``parquet``, ``csv`` or ``both``.
    """

    users: int = DEFAULT_USERS
    months: int = DEFAULT_MONTHS
    sample_frac: float = 1.0
    seed: int = DEFAULT_SEED
    end_date: date = DEFAULT_END_DATE
    monthly_churn_rate: float = DEFAULT_MONTHLY_CHURN_RATE
    reactivation_rate: float = DEFAULT_REACTIVATION_RATE
    power_user_hours: float = POWER_USER_HOURS_PER_DAY
    power_user_days: int = POWER_USER_DAYS_PER_WEEK
    out_dir: str = "data/full"
    output_format: str = "parquet"
    #: Write Hive-partitioned directories (``event_date=.../part-00000.parquet``).
    #: Disable for small committed samples: at ~550 days, per-day partitioning
    #: produces hundreds of tiny files whose parquet footers dwarf the data
    #: (15 MB of files for <1 MB of rows). The declared partitioning still
    #: appears in the manifest and the Unity Catalog DDL either way.
    partitioned: bool = True
    chunk_users: int = 2_500
    campaigns: int = 5
    _validated: bool = field(default=False, repr=False, compare=False)

    # -- derived -----------------------------------------------------------

    def __post_init__(self) -> None:
        if self.users <= 0:
            raise ValueError("users must be positive")
        if self.months < 2:
            raise ValueError("months must be >= 2 (need at least one at-risk month)")
        if not 0 < self.sample_frac <= 1:
            raise ValueError("sample_frac must be in (0, 1]")
        if not 0 < self.monthly_churn_rate < 0.5:
            raise ValueError("monthly_churn_rate must be in (0, 0.5)")
        if not 0 < self.reactivation_rate < 1:
            raise ValueError("reactivation_rate must be in (0, 1)")
        if self.output_format not in ("parquet", "csv", "both"):
            raise ValueError("output_format must be parquet, csv or both")
        if not 4 <= self.campaigns <= 6:
            raise ValueError("campaigns must be between 4 and 6 (brief: ~4-6)")

    @property
    def n_users(self) -> int:
        """Effective user count after applying ``sample_frac`` (always >= 1)."""
        return max(1, int(round(self.users * self.sample_frac)))

    @property
    def window_end(self) -> pd.Timestamp:
        return pd.Timestamp(self.end_date)

    @property
    def window_start(self) -> pd.Timestamp:
        """First day of the earliest whole month in the window."""
        last_month_start = self.window_end.replace(day=1)
        return last_month_start - pd.DateOffset(months=self.months - 1)

    @property
    def n_days(self) -> int:
        return int((self.window_end - self.window_start).days) + 1

    @property
    def days(self) -> pd.DatetimeIndex:
        return pd.date_range(self.window_start, self.window_end, freq="D")

    @property
    def month_starts(self) -> pd.DatetimeIndex:
        return pd.date_range(self.window_start, periods=self.months, freq="MS")

    def replace(self, **changes: object) -> GeneratorConfig:
        """Return a copy with ``changes`` applied (dataclasses.replace shim)."""
        return dataclasses.replace(self, **changes)

    def summary(self) -> dict[str, object]:
        """Flat, text-friendly description of the run (goes into the run log)."""
        return {
            "seed": self.seed,
            "users_requested": self.users,
            "sample_frac": self.sample_frac,
            "users_effective": self.n_users,
            "months": self.months,
            "window_start": str(self.window_start.date()),
            "window_end": str(self.window_end.date()),
            "days": self.n_days,
            "target_monthly_churn_rate": self.monthly_churn_rate,
            "target_reactivation_rate": self.reactivation_rate,
            "power_user_bar": (
                f">={self.power_user_hours} coding hours/day on "
                f">={self.power_user_days} days/week"
            ),
            "campaigns": self.campaigns,
            "output_format": self.output_format,
            "partitioned": self.partitioned,
            "out_dir": self.out_dir,
        }
