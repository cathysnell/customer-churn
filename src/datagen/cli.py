"""CLI entrypoint: ``python -m datagen``.

Examples::

    # Small, fast run — this is what the committed sample + evidence come from.
    python -m datagen --sample-frac 0.006 --months 12 \
        --out data/sample --format csv --evidence evidence/datagen-run.md

    # Full scale: 50,000 users x 18 months of daily history.
    python -m datagen --out data/full --format parquet

    # Just print the schema, no generation.
    python -m datagen --dictionary-only
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import sys
import tempfile
from datetime import date
from pathlib import Path

from datagen.config import (
    DEFAULT_END_DATE,
    DEFAULT_MONTHLY_CHURN_RATE,
    DEFAULT_MONTHS,
    DEFAULT_REACTIVATION_RATE,
    DEFAULT_SEED,
    DEFAULT_USERS,
    GeneratorConfig,
)
from datagen.evidence import render_data_dictionary, render_evidence
from datagen.pipeline import GenerationResult, generate, validate
from datagen.writer import checksum_files, checksum_frames, write_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m datagen",
        description=(
            "Generate the synthetic developer-behavior dataset for the churn / "
            "retention demo. Synthetic data only — no real customer data."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    volume = parser.add_argument_group("volume knobs")
    volume.add_argument(
        "--users",
        type=int,
        default=DEFAULT_USERS,
        help="Pro-tier users to generate, before --sample-frac is applied.",
    )
    volume.add_argument(
        "--months",
        type=int,
        default=DEFAULT_MONTHS,
        help="Whole months of daily history to generate.",
    )
    volume.add_argument(
        "--sample-frac",
        type=float,
        default=1.0,
        help=(
            "Scale --users by this fraction for a fast small run. Days are never "
            "truncated, so behavioural trends stay intact at any fraction."
        ),
    )
    volume.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Master random seed. The committed default is the reproducible one.",
    )
    volume.add_argument(
        "--end-date",
        type=_parse_date,
        default=DEFAULT_END_DATE,
        help="Last day of the observation window (YYYY-MM-DD). Never today().",
    )
    volume.add_argument(
        "--chunk-users",
        type=int,
        default=2500,
        help="Users per chunk when generating daily rows (memory / speed tradeoff).",
    )

    realism = parser.add_argument_group("realism knobs")
    realism.add_argument(
        "--churn-rate",
        type=float,
        default=DEFAULT_MONTHLY_CHURN_RATE,
        help="Target mean monthly churn rate; the hazard intercept is calibrated to it.",
    )
    realism.add_argument(
        "--reactivation-rate",
        type=float,
        default=DEFAULT_REACTIVATION_RATE,
        help="Target CRM reactivation rate for a delivered winback touch.",
    )
    realism.add_argument(
        "--campaigns",
        type=int,
        default=5,
        help="Number of CRM campaigns to run (4-6).",
    )

    output = parser.add_argument_group("output")
    output.add_argument(
        "--out",
        default="data/full",
        help="Directory to write partitioned table files into.",
    )
    output.add_argument(
        "--format",
        dest="output_format",
        choices=("parquet", "csv", "both"),
        default="parquet",
        help="Output file format.",
    )
    output.add_argument(
        "--no-partitions",
        action="store_true",
        help=(
            "Write one file per table instead of Hive-partitioned directories. "
            "Use for small committed samples: per-day partitioning of a long "
            "window creates hundreds of tiny files whose parquet footers dwarf "
            "the data. Partition columns stay in the file bodies."
        ),
    )
    output.add_argument(
        "--evidence",
        type=Path,
        default=None,
        help="Write the markdown execution-evidence report to this path.",
    )
    output.add_argument(
        "--verify-reproducible",
        action="store_true",
        help=(
            "Regenerate the whole dataset a second time into a temporary "
            "directory and compare both the canonical content digests and the "
            "emitted Parquet bytes. Records the outcome in the evidence report "
            "(section 9c) and exits non-zero on a mismatch."
        ),
    )
    output.add_argument(
        "--no-write",
        action="store_true",
        help="Generate and validate in memory without writing data files.",
    )
    output.add_argument(
        "--dictionary-only",
        action="store_true",
        help="Print the data dictionary and exit without generating anything.",
    )
    output.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the progress log on stderr.",
    )
    return parser


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.dictionary_only:
        sys.stdout.write(render_data_dictionary())
        return 0

    config = GeneratorConfig(
        users=args.users,
        months=args.months,
        sample_frac=args.sample_frac,
        seed=args.seed,
        end_date=args.end_date,
        monthly_churn_rate=args.churn_rate,
        reactivation_rate=args.reactivation_rate,
        out_dir=args.out,
        output_format=args.output_format,
        partitioned=not args.no_partitions,
        chunk_users=args.chunk_users,
        campaigns=args.campaigns,
    )

    log_buffer = io.StringIO()
    _configure_logging(log_buffer, quiet=args.quiet)
    logger = logging.getLogger("datagen")
    logger.info("datagen starting | %s", _one_line(config))

    result = generate(config)

    manifest = None
    if not args.no_write:
        manifest = write_all(result.frames, config)

    checks = validate(result)
    for line in checks:
        logger.info("check: %s", line)
    failures = [line for line in checks if "FAIL" in line]

    logger.info(
        "monthly churn rate: %.4f (target %.4f) | users %s | usage_events %s rows",
        result.monthly_churn_rate,
        config.monthly_churn_rate,
        f"{len(result.frames['users']):,}",
        f"{len(result.frames['usage_events']):,}",
    )
    logger.info(
        "churn detail: %d churn events / %d at-risk user-months = %.6f",
        int(result.frames["churn_labels"]["churned"].sum()),
        len(result.frames["churn_labels"]),
        result.monthly_churn_rate,
    )
    logger.info("datagen finished | total rows %s", f"{sum(result.row_counts.values()):,}")

    file_digests = checksum_files(config.out_dir) if not args.no_write else None
    two_run = None
    if args.verify_reproducible:
        two_run = _verify_reproducible(config, result, file_digests, logger)

    if args.evidence:
        command = _reconstruct_command(argv)
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            render_evidence(
                result,
                manifest=manifest,
                run_log=log_buffer.getvalue(),
                command=command,
                file_digests=file_digests,
                two_run=two_run,
            )
        )
        logger.info("wrote evidence -> %s", args.evidence)

    if two_run is not None and not (two_run["content_match"] and two_run["files_match"]):
        logger.error("reproducibility verification FAILED")
        return 1

    if failures:
        logger.error("%d consistency check(s) FAILED", len(failures))
        return 1
    return 0


def _verify_reproducible(
    config: GeneratorConfig,
    result: GenerationResult,
    file_digests: dict[str, str] | None,
    logger: logging.Logger,
) -> dict[str, object]:
    """Regenerate into a temp dir and compare digests against the first run.

    Proves reproducibility *from the committed artifact itself* rather than
    asserting it in prose: the second run writes to a different directory, so any
    hidden dependence on wall-clock time, hash randomization or output path would
    surface as a mismatch here.
    """
    logger.info("verifying reproducibility: regenerating into a temporary directory")
    run1_content = checksum_frames(result.frames)

    with tempfile.TemporaryDirectory(prefix="datagen-verify-") as tmp:
        second_config = config.replace(out_dir=tmp)
        second = generate(second_config)
        run2_content = checksum_frames(second.frames)
        run2_files = None
        if file_digests is not None:
            write_all(second.frames, second_config)
            run2_files = checksum_files(tmp)

    content_match = run1_content == run2_content
    files_match = file_digests is None or run2_files == file_digests

    logger.info(
        "reproducibility: content digests %s | parquet byte digests %s",
        "MATCH" if content_match else "MISMATCH",
        "MATCH" if files_match else "MISMATCH" if file_digests is not None else "n/a",
    )

    return {
        "run1_dir": config.out_dir,
        "run2_dir": "<temporary directory, removed after comparison>",
        "tables": len(run1_content),
        "content_match": content_match,
        "files": len(file_digests) if file_digests else 0,
        "files_match": files_match,
        "run1_content_combined": _combine(run1_content),
        "run2_content_combined": _combine(run2_content),
        "run1_files_combined": _combine(file_digests or {}),
        "run2_files_combined": _combine(run2_files or {}),
    }


def _combine(digests: dict[str, str]) -> str:
    """Fold a name->digest map into one SHA-256, so the whole set is one line.

    Names are included and sorted, so a renamed or missing file changes the
    combined value rather than silently cancelling out.
    """
    if not digests:
        return "(none)"
    joined = "\n".join(f"{name}:{digest}" for name, digest in sorted(digests.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _configure_logging(buffer: io.StringIO, *, quiet: bool) -> None:
    """Log to stderr and to an in-memory buffer (the buffer goes into evidence)."""
    logger = logging.getLogger("datagen")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")

    buffer_handler = logging.StreamHandler(buffer)
    buffer_handler.setFormatter(formatter)
    logger.addHandler(buffer_handler)

    if not quiet:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(formatter)
        logger.addHandler(stderr_handler)


def _one_line(config: GeneratorConfig) -> str:
    return " ".join(f"{k}={v}" for k, v in config.summary().items())


def _reconstruct_command(argv: list[str] | None) -> str:
    argv = argv if argv is not None else sys.argv[1:]
    return "python -m datagen " + " ".join(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
