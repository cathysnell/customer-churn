"""Shared fixtures.

Generation is the expensive part of every test, so the two shared runs are
session-scoped and reused. ``SMALL`` is deliberately big enough for the
statistical assertions (churn band, signal correlation) to be stable at the
committed seed while still finishing in a couple of seconds.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow `pytest` to work without an editable install.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from datagen.config import GeneratorConfig  # noqa: E402
from datagen.pipeline import GenerationResult, generate  # noqa: E402

#: Users for the shared statistical run. Large enough that the churn rate and
#: cohort comparisons are not seed-luck, small enough to stay fast.
SMALL_USERS = 1200
SMALL_MONTHS = 12


@pytest.fixture(scope="session")
def small_config(tmp_path_factory: pytest.TempPathFactory) -> GeneratorConfig:
    out = tmp_path_factory.mktemp("datagen-small")
    return GeneratorConfig(
        users=SMALL_USERS,
        months=SMALL_MONTHS,
        out_dir=str(out / "data"),
        output_format="parquet",
    )


@pytest.fixture(scope="session")
def result(small_config: GeneratorConfig) -> GenerationResult:
    """One generated dataset shared by every read-only test."""
    return generate(small_config)


@pytest.fixture(scope="session")
def frames(result: GenerationResult) -> dict:
    return result.frames


@pytest.fixture
def tiny_config(tmp_path: Path) -> GeneratorConfig:
    """A fast config for tests that need to generate more than once."""
    return GeneratorConfig(
        users=150,
        months=4,
        out_dir=str(tmp_path / "data"),
        output_format="parquet",
    )
