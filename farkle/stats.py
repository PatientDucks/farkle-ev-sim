"""Exact (not simulated) probability calculations via full enumeration.

Six dice has only 6**6 = 46,656 possible outcomes, small enough to enumerate
directly, so bust probability is computed exactly rather than estimated,
giving a precise reference figure to sit alongside the Monte Carlo EV
numbers.
"""

from __future__ import annotations

from functools import lru_cache
from itertools import product

from .rules import best_score


@lru_cache(maxsize=None)
def bust_probability(dice_remaining: int) -> float:
    outcomes = list(product(range(1, 7), repeat=dice_remaining))
    busts = sum(1 for dice in outcomes if best_score(dice)[0] == 0)
    return busts / len(outcomes)


@lru_cache(maxsize=None)
def expected_score_per_roll(dice_remaining: int) -> float:
    """Exact expected score from a single roll of `dice_remaining` dice,
    counting busts as zero (does not account for continuing afterward)."""
    outcomes = list(product(range(1, 7), repeat=dice_remaining))
    total = sum(best_score(dice)[0] for dice in outcomes)
    return total / len(outcomes)
