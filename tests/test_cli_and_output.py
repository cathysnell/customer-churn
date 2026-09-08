"""CLI behaviour, volume knobs, and written output (files, manifest, DDL, evidence)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from datagen import schemas
from datagen.cli import main
from datagen.config import DEFAULT_SEED, DEFAULT_USERS, GeneratorConfig
from datagen.evidence import render_evidence
from datagen.pipeline import GenerationResult, generate
from datagen.writer import unity_catalog_ddl, write_all

# ---------------------------------------------------------------------------
# Volume knobs
# ---------------------------------------------------------------------------


def test_sample_frac_scales_the_user_count() -> None:
    config = GeneratorConfig(users=10_000, sample_frac=0.01)
    assert config.n_users == 100


def test_sample_frac_never_yields_zero_users() -> None:
    """A tiny fraction must still produce a runnable dataset, not an empty one."""
    config = GeneratorConfig(users=10, sample_frac=0.0001)
    assert config.n_users == 1


def test_sample_frac_produces_a_smaller_dataset(tmp_path: Path) -> None:
    base = GeneratorConfig(users=400, months=4, out_dir=str(tmp_path / "a"))
    sampled = GeneratorConfig(
        users=400, months=4, sample_frac=0.25, out_dir=str(tmp_path / "b")
    )
    full_rows = len(generate(base).frames["usage_events"])
    sample_rows = len(generate(sampled).frames["usage_events"])
    assert 0 < sample_rows < full_rows


def test_sample_frac_does_not_truncate_the_time_window(tmp_path: Path) -> None:
    """Sampling drops users, never days — trends must survive a small run."""
    sampled = GeneratorConfig(
        users=800, months=6, sample_frac=0.05, out_dir=str(tmp_path / "s")
    )
    result = generate(sampled)
    events = result.frames["usage_events"]
    assert events["event_date"].min() >= sampled.window_start
    assert events["event_date"].max() <= sampled.window_end
    # Every month of the window is represented in the labels.
    assert result.frames["churn_labels"]["month_start"].nunique() == sampled.months


def test_months_knob_changes_the_window_length() -> None:
    short = GeneratorConfig(months=6)
    long = GeneratorConfig(months=18)
    assert short.n_days < long.n_days
    assert len(short.month_starts) == 6
    assert len(long.month_starts) == 18


def test_default_volume_matches_the_brief() -> None:
    """Brief: 50,000 Pro users x 18 months of daily history, ~547 days."""
    config = GeneratorConfig()
    assert config.users == DEFAULT_USERS == 50_000
    assert config.months == 18
    assert config.seed == DEFAULT_SEED
    assert 540 <= config.n_days <= 550


def test_window_end_is_fixed_not_today() -> None:
    """A committed end date is what makes regeneration reproducible."""
    assert GeneratorConfig().end_date == date(2026, 8, 31)
    assert GeneratorConfig().end_date != date.today()


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"users": 0}, "users must be positive"),
        ({"months": 1}, "months must be"),
        ({"sample_frac": 0.0}, "sample_frac"),
        ({"sample_frac": 1.5}, "sample_frac"),
        ({"monthly_churn_rate": 0.9}, "monthly_churn_rate"),
        ({"reactivation_rate": 0.0}, "reactivation_rate"),
        ({"output_format": "avro"}, "output_format"),
        ({"campaigns": 2}, "campaigns"),
    ],
)
def test_invalid_config_is_rejected(kwargs: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        GeneratorConfig(**kwargs)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_write_all_writes_every_table(tmp_path: Path) -> None:
    config = GeneratorConfig(users=120, months=3, out_dir=str(tmp_path / "data"))
    result = generate(config)
    manifest = write_all(result.frames, config)

    out = Path(config.out_dir)
    for name in schemas.table_names():
        assert (out / name).is_dir(), f"{name} directory missing"
        assert list((out / name).rglob("*.parquet")), f"{name} has no parquet files"

    assert manifest["total_rows"] == sum(result.row_counts.values())
    assert {entry["table"] for entry in manifest["tables"]} == set(schemas.table_names())


def test_written_parquet_round_trips(tmp_path: Path) -> None:
    """Reading the files back must reproduce the row counts the manifest claims."""
    config = GeneratorConfig(users=120, months=3, out_dir=str(tmp_path / "data"))
    result = generate(config)
    write_all(result.frames, config)

    out = Path(config.out_dir)
    for name in schemas.table_names():
        files = sorted((out / name).rglob("*.parquet"))
        rows = sum(len(pd.read_parquet(f)) for f in files)
        assert rows == len(result.frames[name]), f"{name} row count changed on disk"


def test_partitioned_tables_use_hive_layout(tmp_path: Path) -> None:
    """Partition columns live in the path and are dropped from the file bodies."""
    config = GeneratorConfig(users=120, months=3, out_dir=str(tmp_path / "data"))
    result = generate(config)
    write_all(result.frames, config)

    out = Path(config.out_dir)
    for spec in schemas.TABLES:
        if not spec.partition_by:
            continue
        files = list((out / spec.name).rglob("*.parquet"))
        assert files, f"{spec.name} not written"
        for column in spec.partition_by:
            assert any(f"{column}=" in str(f) for f in files)
        body = pd.read_parquet(files[0])
        for column in spec.partition_by:
            assert column not in body.columns


def test_manifest_records_seed_and_config(tmp_path: Path) -> None:
    config = GeneratorConfig(users=100, months=3, out_dir=str(tmp_path / "data"))
    result = generate(config)
    write_all(result.frames, config)

    manifest = json.loads((Path(config.out_dir) / "_manifest.json").read_text())
    assert manifest["config"]["seed"] == config.seed
    assert manifest["config"]["users_effective"] == config.n_users
    assert manifest["unity_catalog"]["format_intent"] == "delta"


def test_csv_format_is_supported(tmp_path: Path) -> None:
    """CSV keeps the committed sample readable as text in the repo."""
    config = GeneratorConfig(
        users=60, months=3, out_dir=str(tmp_path / "data"), output_format="csv"
    )
    result = generate(config)
    write_all(result.frames, config)
    out = Path(config.out_dir)
    assert list(out.rglob("*.csv"))
    assert not list(out.rglob("*.parquet"))


def test_unity_catalog_ddl_covers_every_table() -> None:
    ddl = unity_catalog_ddl(GeneratorConfig())
    for spec in schemas.TABLES:
        assert f".{spec.name} (" in ddl, f"{spec.name} missing from DDL"
        for column in spec.columns:
            assert column.name in ddl
    assert "USING DELTA" in ddl
    assert "CREATE CATALOG IF NOT EXISTS" in ddl
    # Gold-layer tables land in the gold schema, not bronze.
    assert "gold.churn_labels" in ddl
    assert "bronze.usage_events" in ddl


def test_unity_catalog_ddl_declares_keys() -> None:
    ddl = unity_catalog_ddl(GeneratorConfig())
    assert "PRIMARY KEY" in ddl
    assert "FOREIGN KEY" in ddl
    assert "PARTITIONED BY (event_date)" in ddl


# ---------------------------------------------------------------------------
# Evidence rendering
# ---------------------------------------------------------------------------


def test_evidence_contains_the_required_sections(result: GenerationResult) -> None:
    """The evaluator reads text only, so the evidence must carry the real numbers."""
    text = render_evidence(result, command="python -m datagen --sample-frac 0.01")

    for needle in [
        "Row counts",
        "Data dictionary",
        "head(",
        "Summary statistics",
        "Churn-signal realism check",
        "Per-geography breakdown",
        "Determinism",
        "Synthetic data only",
    ]:
        assert needle in text, f"evidence missing {needle!r}"

    for name in schemas.table_names():
        assert f"`{name}`" in text
    # The realised churn rate must be printed, not just described.
    assert f"{result.monthly_churn_rate:.3%}" in text


def test_evidence_includes_every_column_description() -> None:
    from datagen.evidence import render_data_dictionary

    text = render_data_dictionary()
    for spec in schemas.TABLES:
        for column in spec.columns:
            assert column.name in text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_runs_end_to_end_and_writes_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.md"
    exit_code = main(
        [
            "--users",
            "150",
            "--months",
            "4",
            "--out",
            str(tmp_path / "data"),
            "--format",
            "csv",
            "--evidence",
            str(evidence),
            "--quiet",
        ]
    )
    assert exit_code == 0
    assert evidence.is_file()
    text = evidence.read_text()
    assert "Console log from the run" in text
    assert "Output manifest" in text
    assert list((tmp_path / "data").rglob("*.csv"))


def test_cli_no_write_skips_files(tmp_path: Path) -> None:
    out = tmp_path / "data"
    assert main(["--users", "80", "--months", "3", "--out", str(out), "--no-write", "--quiet"]) == 0
    assert not out.exists()


def test_cli_dictionary_only_prints_schema(capsys: pytest.CaptureFixture) -> None:
    assert main(["--dictionary-only"]) == 0
    printed = capsys.readouterr().out
    assert "usage_events" in printed
    assert "ai_suggestion_acceptance_rate" in printed


def test_cli_sample_frac_flag_is_wired(tmp_path: Path) -> None:
    """The flag the demo relies on must actually shrink the run."""
    assert (
        main(
            [
                "--users",
                "2000",
                "--sample-frac",
                "0.05",
                "--months",
                "3",
                "--out",
                str(tmp_path / "d"),
                "--quiet",
            ]
        )
        == 0
    )
    users = pd.read_parquet(next((tmp_path / "d" / "users").rglob("*.parquet")))
    assert len(users) <= 100


def test_cli_seed_flag_is_wired(tmp_path: Path) -> None:
    def run(seed: int, name: str) -> pd.DataFrame:
        assert (
            main(
                [
                    "--users",
                    "80",
                    "--months",
                    "3",
                    "--seed",
                    str(seed),
                    "--out",
                    str(tmp_path / name),
                    "--quiet",
                ]
            )
            == 0
        )
        files = sorted((tmp_path / name / "users").rglob("*.parquet"))
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    a = run(1, "one")
    b = run(2, "two")
    assert not a.equals(b)


def test_cli_help_documents_the_knobs(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    printed = capsys.readouterr().out
    for flag in ["--sample-frac", "--users", "--months", "--seed", "--out", "--evidence"]:
        assert flag in printed
