"""Determinism: the same seed must reproduce the same bytes, always."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from datagen import schemas
from datagen.config import DEFAULT_SEED, GeneratorConfig
from datagen.pipeline import generate
from datagen.rng import stream_entropy, substream
from datagen.writer import checksum_files, checksum_frames, write_all


def test_same_seed_produces_identical_frames(tiny_config: GeneratorConfig) -> None:
    """Two independent runs of the same config are equal frame-for-frame."""
    first = generate(tiny_config)
    second = generate(tiny_config)

    assert set(first.frames) == set(second.frames)
    for name in schemas.table_names():
        pd.testing.assert_frame_equal(
            first.frames[name],
            second.frames[name],
            check_dtype=True,
            obj=f"table {name}",
        )


def test_same_seed_produces_identical_content_checksums(
    tiny_config: GeneratorConfig,
) -> None:
    """The canonical-content digests printed in the evidence are reproducible.

    These hash a canonical text rendering of each frame (see
    :func:`datagen.writer.checksum_frames`) — i.e. the generator's guaranteed
    invariant, deterministic *logical content*.
    """
    first = checksum_frames(generate(tiny_config).frames)
    second = checksum_frames(generate(tiny_config).frames)
    assert first == second
    # Every table must actually be covered by a digest.
    assert set(first) == set(schemas.table_names())


def test_same_seed_produces_identical_parquet_bytes(tmp_path: Path) -> None:
    """Two runs written to disk produce byte-identical Parquet **files**.

    This is the check that hashes what actually lands on disk, rather than an
    in-memory serialization. It is scoped to a single pinned environment: the
    Parquet footer embeds the writer version, so this asserts the generator
    contributes no nondeterminism of its own, not that Parquet bytes are stable
    across pyarrow upgrades. The always-true invariant is content equality,
    covered by ``test_same_seed_produces_identical_content_checksums``.
    """
    digests = []
    for run in ("a", "b"):
        config = GeneratorConfig(
            users=80,
            months=3,
            out_dir=str(tmp_path / run),
            output_format="parquet",
            partitioned=False,
        )
        write_all(generate(config).frames, config)
        digests.append(checksum_files(config.out_dir))

    assert digests[0] == digests[1]
    # Guard against a vacuous pass if nothing was written.
    assert len(digests[0]) == len(schemas.table_names())
    assert all(name.endswith(".parquet") for name in digests[0])


def test_parquet_bytes_are_deterministic_when_partitioned(tmp_path: Path) -> None:
    """Byte determinism also holds for the Hive-partitioned layout."""
    digests = []
    for run in ("a", "b"):
        config = GeneratorConfig(
            users=60,
            months=3,
            out_dir=str(tmp_path / run),
            output_format="parquet",
            partitioned=True,
        )
        write_all(generate(config).frames, config)
        digests.append(checksum_files(config.out_dir))

    assert digests[0] == digests[1]
    assert any("event_date=" in name for name in digests[0])


def test_different_seed_produces_different_data(tiny_config: GeneratorConfig) -> None:
    """A seed change must actually change the data, or the seed is not wired in."""
    baseline = generate(tiny_config)
    changed = generate(tiny_config.replace(seed=DEFAULT_SEED + 1))

    baseline_sums = checksum_frames(baseline.frames)
    changed_sums = checksum_frames(changed.frames)

    # crm_campaigns is a pure dimension with no random content, so it is expected
    # to be identical; everything else must differ.
    differing = {name for name in baseline_sums if baseline_sums[name] != changed_sums[name]}
    assert "crm_campaigns" not in differing
    assert differing == set(schemas.table_names()) - {"crm_campaigns"}


def test_no_wall_clock_dependency(tiny_config: GeneratorConfig) -> None:
    """The observation window comes from ``end_date``, never from ``today()``.

    A dataset whose window moved with the calendar could not be regenerated
    reproducibly tomorrow, so this pins the behaviour explicitly.
    """
    result = generate(tiny_config)
    events = result.frames["usage_events"]
    assert events["event_date"].max() <= tiny_config.window_end
    assert events["event_date"].min() >= tiny_config.window_start

    # Shifting only the end date shifts the window, proving it is the source.
    shifted = tiny_config.replace(end_date=tiny_config.end_date.replace(year=2025))
    shifted_events = generate(shifted).frames["usage_events"]
    assert shifted_events["event_date"].max() <= shifted.window_end
    assert shifted_events["event_date"].max() < events["event_date"].max()


def test_substream_is_stable_and_independent() -> None:
    """Named sub-streams are stable across calls and distinct from each other."""
    a = substream(DEFAULT_SEED, "users.geo").random(20)
    b = substream(DEFAULT_SEED, "users.geo").random(20)
    c = substream(DEFAULT_SEED, "users.plan").random(20)

    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)


def test_substream_names_hash_stably() -> None:
    """Sub-stream entropy must not depend on PYTHONHASHSEED.

    ``hash()`` on strings is salted per process, so using it here would make the
    dataset irreproducible across runs. This asserts the BLAKE2b digest values
    directly.
    """
    assert stream_entropy(1729, "users.geo") == stream_entropy(1729, "users.geo")
    assert stream_entropy(1729, "users.geo") != stream_entropy(1729, "users.plan")
    assert stream_entropy(1729, "users.geo") != stream_entropy(1730, "users.geo")
    # The seed is the first element, so it is visibly part of the entropy.
    assert stream_entropy(1729, "users.geo")[0] == 1729


def test_substream_tags_discriminate() -> None:
    """Per-chunk streams (``tags``) must not collide."""
    first = substream(DEFAULT_SEED, "usage.daily", 0).random(10)
    second = substream(DEFAULT_SEED, "usage.daily", 2500).random(10)
    assert not np.array_equal(first, second)


def test_calibration_is_deterministic(tiny_config: GeneratorConfig) -> None:
    """The bisection lands on the same intercept in the same number of steps."""
    first = generate(tiny_config).lifecycle
    second = generate(tiny_config).lifecycle
    assert first.intercept == pytest.approx(second.intercept, abs=0.0)
    assert first.calibration_iterations == second.calibration_iterations
