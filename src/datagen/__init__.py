"""Synthetic developer-behavior dataset generator.

Generates the raw dataset for the Developer Behavioral Analytics Platform
(churn / retention prediction) demo. **Synthetic only — zero real customer
data.** Every table is derived from a single committed random seed, so the
whole dataset regenerates deterministically from code.

Public entrypoints:
    generate(config)   -> dict[str, pandas.DataFrame]
    GeneratorConfig    -> volume / realism knobs
    main()             -> CLI (``python -m datagen``)
"""

from datagen.config import DEFAULT_SEED, GeneratorConfig
from datagen.pipeline import generate
from datagen.schemas import TABLES, table_names

__all__ = [
    "DEFAULT_SEED",
    "TABLES",
    "GeneratorConfig",
    "generate",
    "table_names",
]

__version__ = "0.1.0"
