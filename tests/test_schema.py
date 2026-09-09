"""Schema conformance: every table has exactly the declared columns and dtypes."""

from __future__ import annotations

import pandas as pd
import pytest

from datagen import schemas
from datagen.pipeline import conform
from datagen.schemas import TABLES, TableSpec

TABLE_IDS = [spec.name for spec in TABLES]


def test_all_expected_tables_are_emitted(frames: dict) -> None:
    """The brief names eight tables; the generator must emit exactly those."""
    assert set(frames) == {
        "users",
        "subscriptions",
        "usage_events",
        "feature_adoption",
        "support_tickets",
        "crm_campaigns",
        "crm_touches",
        "churn_labels",
    }
    assert set(frames) == set(schemas.table_names())


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_columns_match_spec_exactly_and_in_order(spec: TableSpec, frames: dict) -> None:
    """Column presence *and* order match the spec, so parquet readers are stable."""
    assert list(frames[spec.name].columns) == list(spec.column_names)


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_dtypes_match_spec(spec: TableSpec, frames: dict) -> None:
    frame = frames[spec.name]
    for column in spec.columns:
        actual = str(frame[column.name].dtype)
        expected = column.pandas_dtype
        if expected == "string":
            # Python strings live in object columns in pandas 2.x.
            assert actual == "object", f"{spec.name}.{column.name} is {actual}"
        else:
            assert actual == expected, f"{spec.name}.{column.name} is {actual}, want {expected}"


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_non_nullable_columns_have_no_nulls(spec: TableSpec, frames: dict) -> None:
    frame = frames[spec.name]
    for column in spec.columns:
        if column.nullable:
            continue
        assert not frame[column.name].isna().any(), f"{spec.name}.{column.name} has nulls"


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_tables_are_non_empty(spec: TableSpec, frames: dict) -> None:
    """An empty table would silently starve a downstream stage."""
    assert len(frames[spec.name]) > 0, f"{spec.name} is empty"


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_primary_key_is_unique(spec: TableSpec, frames: dict) -> None:
    frame = frames[spec.name]
    dupes = frame.duplicated(subset=list(spec.primary_key)).sum()
    assert dupes == 0, f"{spec.name} has {dupes} duplicate {spec.primary_key} rows"


@pytest.mark.parametrize("spec", TABLES, ids=TABLE_IDS)
def test_every_column_is_documented(spec: TableSpec) -> None:
    """The data dictionary in the evidence is only useful if descriptions exist."""
    for column in spec.columns:
        assert column.description.strip(), f"{spec.name}.{column.name} has no description"
        assert column.sql_type, f"{spec.name}.{column.name} has no SQL type"
    assert spec.grain.strip()
    assert spec.description.strip()
    assert spec.asset.strip()


def test_conform_rejects_missing_column() -> None:
    """`conform` is the schema gate; it must fail loudly, not coerce silently."""
    with pytest.raises(ValueError, match="missing columns"):
        conform("users", pd.DataFrame({"user_id": ["USR-1"]}))


def test_conform_rejects_unexpected_column(frames: dict) -> None:
    broken = frames["users"].copy()
    broken["surprise"] = 1
    with pytest.raises(ValueError, match="unexpected columns"):
        conform("users", broken)


def test_conform_rejects_null_in_non_nullable_column(frames: dict) -> None:
    broken = frames["users"].copy()
    broken.loc[broken.index[0], "geo"] = None
    with pytest.raises(ValueError, match="non-nullable"):
        conform("users", broken)


def test_spec_lookup_rejects_unknown_table() -> None:
    with pytest.raises(KeyError):
        schemas.spec("not_a_table")


def test_declared_foreign_keys_reference_real_tables() -> None:
    """Guards the generated Unity Catalog DDL against dangling references."""
    for spec in TABLES:
        for column, target in spec.foreign_keys:
            assert column in spec.column_names
            target_table, target_column = target.split(".")
            target_spec = schemas.spec(target_table)
            assert target_column in target_spec.column_names
            assert target_spec.primary_key == (target_column,)


def test_partition_columns_exist_in_their_table() -> None:
    for spec in TABLES:
        for column in spec.partition_by:
            assert column in spec.column_names, f"{spec.name} partitions on missing {column}"
