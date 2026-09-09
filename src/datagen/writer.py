"""Writing tables to disk, plus Unity Catalog registration intent.

Output layout under ``out_dir`` (gitignored — no data artifact is ever committed;
the dataset is regenerated from the committed seed instead)::

    data/sample/
      users/geo=NA/part-00000.parquet        # partitioned tables
      usage_events/event_date=2025-03-01/...
      subscriptions/part-00000.parquet       # unpartitioned tables
      _manifest.json                         # row counts, seed, config, checksums
      _unity_catalog.sql                     # CREATE TABLE DDL for the UC stage

The manifest and the DDL are the handoff to the next stages: Lakeflow reads the
files from this directory (or a Databricks Volume it was written to), Unity Catalog
runs the DDL. The DDL is also committed as text at ``sql/unity_catalog.sql`` since
it derives purely from :mod:`datagen.schemas` and needs no data to produce.
Nothing here talks to Databricks — the generator must run on a laptop with only
numpy/pandas/pyarrow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

import pandas as pd

from datagen import schemas
from datagen.config import GeneratorConfig

LOGGER = logging.getLogger("datagen.writer")

#: Target catalog/schema for the Unity Catalog stage. Declared here so the DDL
#: this module emits and the later UC stage agree on one name.
UC_CATALOG = "dev_behavior"
UC_SCHEMA = "bronze"
UC_GOLD_SCHEMA = "gold"


def write_all(
    frames: dict[str, pd.DataFrame],
    config: GeneratorConfig,
    *,
    clean: bool = True,
) -> dict[str, object]:
    """Write every table under ``config.out_dir`` and return the manifest dict."""
    out_dir = Path(config.out_dir)
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, object]] = []
    for name in schemas.table_names():
        spec = schemas.spec(name)
        frame = frames[name]
        files = _write_table(
            frame, spec, out_dir, config.output_format, partitioned=config.partitioned
        )
        entries.append(
            {
                "table": name,
                "asset": spec.asset,
                "layer": spec.layer,
                "grain": spec.grain,
                "rows": int(len(frame)),
                "columns": list(spec.column_names),
                "partition_by": list(spec.partition_by),
                "partitions_written": bool(spec.partition_by and config.partitioned),
                "files": [str(p.relative_to(out_dir)) for p in files],
                "bytes": int(sum(p.stat().st_size for p in files)),
            }
        )
        LOGGER.info("wrote %-18s %10s rows -> %d file(s)", name, f"{len(frame):,}", len(files))

    manifest = {
        "generator_version": _version(),
        "config": config.summary(),
        "unity_catalog": {
            "catalog": UC_CATALOG,
            "bronze_schema": UC_SCHEMA,
            "gold_schema": UC_GOLD_SCHEMA,
            "format_intent": "delta",
            "ddl_file": "_unity_catalog.sql",
        },
        "tables": entries,
        "total_rows": int(sum(e["rows"] for e in entries)),
    }
    manifest_path = out_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n")

    ddl_path = out_dir / "_unity_catalog.sql"
    ddl_path.write_text(unity_catalog_ddl(config))
    LOGGER.info("wrote manifest -> %s", manifest_path)
    LOGGER.info("wrote Unity Catalog DDL -> %s", ddl_path)
    return manifest


def _version() -> str:
    from datagen import __version__

    return __version__


def _write_table(
    frame: pd.DataFrame,
    spec: schemas.TableSpec,
    out_dir: Path,
    output_format: str,
    *,
    partitioned: bool = True,
) -> list[Path]:
    """Write one table, partitioned if its spec declares partition columns.

    When ``partitioned`` is False the table is written as a single file with the
    partition columns retained in the body, so no information is lost — only the
    directory layout differs.
    """
    table_dir = out_dir / spec.name
    table_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if spec.partition_by and partitioned and not frame.empty:
        for keys, part in frame.groupby(list(spec.partition_by), sort=True, observed=True):
            keys = keys if isinstance(keys, tuple) else (keys,)
            part_dir = table_dir
            for col, value in zip(spec.partition_by, keys, strict=True):
                part_dir = part_dir / f"{col}={_partition_value(value)}"
            part_dir.mkdir(parents=True, exist_ok=True)
            # Partition columns are encoded in the path (Hive convention) and
            # dropped from the file, as Delta/Spark expect.
            payload = part.drop(columns=list(spec.partition_by))
            written += _write_files(payload, part_dir, output_format)
    else:
        written += _write_files(frame, table_dir, output_format)
    return written


def _partition_value(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _write_files(frame: pd.DataFrame, target: Path, output_format: str) -> list[Path]:
    written: list[Path] = []
    if output_format in ("parquet", "both"):
        path = target / "part-00000.parquet"
        # Coerce timestamps to microseconds. pandas date columns are datetime64[ns],
        # which pyarrow serialises as Parquet TIMESTAMP(NANOS); Spark's Parquet reader
        # rejects that with PARQUET_TYPE_ILLEGAL. Our values are day-precision, so the
        # truncation to micros is lossless.
        frame.to_parquet(
            path,
            index=False,
            engine="pyarrow",
            compression="snappy",
            coerce_timestamps="us",
            allow_truncated_timestamps=True,
        )
        written.append(path)
    if output_format in ("csv", "both"):
        path = target / "part-00000.csv"
        frame.to_csv(path, index=False)
        written.append(path)
    return written


def unity_catalog_ddl(config: GeneratorConfig | None = None) -> str:
    """Render ``CREATE TABLE`` DDL registering every table as a Delta table.

    This is *registration intent* for the Unity Catalog stage — the generator
    does not need a Databricks connection to produce it, and the later stage can
    run this file verbatim.

    The DDL is a pure function of :mod:`datagen.schemas`: it depends on the table
    specs only, never on how much data a particular run produced. ``config`` is
    therefore optional and unused — kept in the signature so ``write_all`` can
    pass its config without callers needing to care. The committed copy at
    ``sql/unity_catalog.sql`` is byte-identical to what any run emits, which
    ``tests/test_cli_and_output.py`` asserts so the two cannot drift.
    """
    _ = config
    lines: list[str] = [
        "-- Unity Catalog registration intent for the synthetic developer-behavior dataset.",
        "-- Generated by src/datagen (datagen.writer.unity_catalog_ddl). Synthetic data only.",
        "-- Derived purely from src/datagen/schemas.py: identical for every run,",
        "-- independent of seed, user count, month count or sample fraction.",
        "-- Regenerate with: python -m datagen --emit-ddl sql/unity_catalog.sql",
        "",
        f"CREATE CATALOG IF NOT EXISTS {UC_CATALOG};",
        f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.{UC_SCHEMA};",
        f"CREATE SCHEMA IF NOT EXISTS {UC_CATALOG}.{UC_GOLD_SCHEMA};",
        "",
    ]

    for spec in schemas.TABLES:
        schema_name = UC_GOLD_SCHEMA if spec.layer == "gold" else UC_SCHEMA
        fqn = f"{UC_CATALOG}.{schema_name}.{spec.name}"
        lines.append(f"-- {spec.name}: {spec.description}")
        lines.append(f"--   data asset: {spec.asset}")
        lines.append(f"--   grain: {spec.grain}")
        lines.append(f"CREATE TABLE IF NOT EXISTS {fqn} (")
        col_lines = []
        for column in spec.columns:
            null_clause = "" if column.nullable else " NOT NULL"
            comment = column.description.replace("'", "''")
            col_lines.append(
                f"  {column.name} {column.sql_type}{null_clause} COMMENT '{comment}'"
            )
        lines.append(",\n".join(col_lines))
        lines.append(")")
        lines.append("USING DELTA")
        if spec.partition_by:
            lines.append(f"PARTITIONED BY ({', '.join(spec.partition_by)})")
        table_comment = spec.description.replace("'", "''")
        lines.append(f"COMMENT '{table_comment}'")
        lines.append(";")
        if spec.primary_key:
            pk = ", ".join(spec.primary_key)
            lines.append(
                f"ALTER TABLE {fqn} ADD CONSTRAINT {spec.name}_pk "
                f"PRIMARY KEY ({pk});"
            )
        for column_name, target in spec.foreign_keys:
            target_table, target_column = target.split(".")
            target_schema = (
                UC_GOLD_SCHEMA if schemas.spec(target_table).layer == "gold" else UC_SCHEMA
            )
            constraint = f"{spec.name}_{column_name}_fk"
            lines.append(
                f"ALTER TABLE {fqn} ADD CONSTRAINT {constraint} "
                f"FOREIGN KEY ({column_name}) REFERENCES "
                f"{UC_CATALOG}.{target_schema}.{target_table}({target_column});"
            )
        lines.append("")

    return "\n".join(lines) + "\n"


def checksum_frames(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Per-table SHA-256 over **canonicalized logical content**, not file bytes.

    This is the generator's *guaranteed* determinism invariant: for a fixed seed
    and config, every table's column names, column order, row order and cell
    values are identical. What is hashed is explicitly a canonical text rendering
    of the frame — the header row followed by ``DataFrame.to_csv``, which is
    stable across platforms for the dtypes emitted here (every float is
    pre-rounded, so there are no repr differences).

    It deliberately does **not** hash the emitted Parquet bytes. Those are also
    reproducible in practice — :func:`checksum_files` proves it, and the
    committed evidence records two-run digests — but Parquet byte-equality is a
    property of the *writer*, not of this generator: the file footer embeds the
    pyarrow version string, so upgrading pyarrow changes the bytes while leaving
    the data identical. Logical content is the invariant worth asserting; file
    bytes are verified separately and scoped to a pinned environment.
    """
    out: dict[str, str] = {}
    for name in sorted(frames):
        frame = frames[name]
        digest = hashlib.sha256()
        digest.update(",".join(frame.columns).encode("utf-8"))
        digest.update(frame.to_csv(index=False).encode("utf-8"))
        out[name] = digest.hexdigest()
    return out


def checksum_files(out_dir: str | Path) -> dict[str, str]:
    """SHA-256 of each emitted **data file** under ``out_dir``, keyed by rel path.

    Complements :func:`checksum_frames` by hashing what actually landed on disk.
    Only table data files are hashed: ``_manifest.json`` embeds the absolute
    ``out_dir``, so it differs between two runs written to different directories
    even when the data is identical.
    """
    root = Path(out_dir)
    out: dict[str, str] = {}
    for spec in schemas.TABLES:
        table_dir = root / spec.name
        if not table_dir.is_dir():
            continue
        for path in sorted(table_dir.rglob("*")):
            if not path.is_file():
                continue
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out
