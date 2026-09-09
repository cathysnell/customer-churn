"""Deterministic named random sub-streams.

Every random draw in the generator comes from a *named* sub-stream derived from
the master seed, e.g. ``substream(seed, "users.geo")``. Naming the streams (as
opposed to threading one shared ``Generator`` through the call graph) means that
adding a new draw to one table cannot shift the numbers produced by another —
regenerating after a code change stays reviewable.

Names are hashed with BLAKE2b rather than :func:`hash`, whose string hashing is
salted per interpreter process and would break reproducibility across runs.
"""

from __future__ import annotations

import hashlib

import numpy as np

_DIGEST_BYTES = 8


def stream_entropy(seed: int, name: str) -> list[int]:
    """Return the ``SeedSequence`` entropy for sub-stream ``name`` under ``seed``."""
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=_DIGEST_BYTES).digest()
    return [int(seed), int.from_bytes(digest, "big")]


def substream(seed: int, name: str, *tags: object) -> np.random.Generator:
    """Build an independent generator for ``name`` (plus optional ``tags``).

    Args:
        seed: Master seed from the run config.
        name: Stable, dotted sub-stream name, e.g. ``"usage.daily"``.
        tags: Extra discriminators folded into the name — used for per-chunk
            streams, e.g. ``substream(seed, "usage.daily", chunk_index)``.

    Returns:
        A fresh :class:`numpy.random.Generator`. Two calls with equal arguments
        return generators that produce identical sequences.
    """
    full_name = ".".join([name, *(str(t) for t in tags)])
    return np.random.default_rng(np.random.SeedSequence(stream_entropy(seed, full_name)))


def choice_by_weight(
    rng: np.random.Generator, n: int, weights: dict[str, float]
) -> np.ndarray:
    """Draw ``n`` labels from ``weights`` (keys are labels, values need not sum to 1)."""
    labels = np.array(list(weights.keys()), dtype=object)
    probs = np.array(list(weights.values()), dtype=float)
    probs = probs / probs.sum()
    return labels[rng.choice(len(labels), size=n, p=probs)]


def truncated_lognormal(
    rng: np.random.Generator,
    n: int,
    median: float,
    sigma: float,
    low: float,
    high: float,
) -> np.ndarray:
    """Lognormal draws centred on ``median``, clipped into ``[low, high]``."""
    values = float(median) * np.exp(rng.normal(0.0, sigma, size=n))
    return np.clip(values, low, high)
