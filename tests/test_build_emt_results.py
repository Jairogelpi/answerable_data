from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_emt_results import _binomial_upper_tail


def test_binomial_upper_tail_is_one_at_k_zero() -> None:
    assert _binomial_upper_tail(0, 10, 0.5) == 1.0


def test_binomial_upper_tail_matches_known_value() -> None:
    # P(X >= 1) for X ~ Binomial(1, 0.25) is exactly 0.25.
    assert abs(_binomial_upper_tail(1, 1, 0.25) - 0.25) < 1e-9


def test_binomial_upper_tail_is_tiny_for_extreme_concentration() -> None:
    # 22 of 22 draws landing on a 1/3-probability outcome is astronomically
    # unlikely under a uniform-among-three null -- this is the exact shape
    # of the claim the tool makes about the emt-v1 evidence_invalidation
    # results, so the math backing it gets its own direct test.
    p = _binomial_upper_tail(22, 22, 1 / 3)
    assert p < 1e-9


def test_binomial_upper_tail_handles_zero_trials() -> None:
    assert _binomial_upper_tail(0, 0, 0.5) == 1.0
