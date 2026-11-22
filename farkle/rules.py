"""Farkle scoring rules.

This is the "standard" ruleset used by most digital Farkle implementations.
It's documented in full in the project README; change the constants below
to model different house rules.

    Single 1                       100
    Single 5                       50
    Three of a kind (face v)       1000 if v == 1, else v * 100
    Four of a kind                 2x the three-of-a-kind value
    Five of a kind                 4x the three-of-a-kind value
    Six of a kind                  8x the three-of-a-kind value
    Straight (1-2-3-4-5-6)         1500
    Three pairs                    1500
    Two triplets (two diff. faces) 2500

Entry threshold (500 to get "on the board") and the 10,000-point race are
documented here but not used by the core per-turn EV optimizer, which treats
every banked point as equally valuable; see README for why.
"""

from __future__ import annotations

from collections import Counter

ENTRY_THRESHOLD = 500
WINNING_SCORE = 10_000

STRAIGHT_SCORE = 1500
THREE_PAIRS_SCORE = 1500
ENABLE_TWO_TRIPLETS_BONUS = True
TWO_TRIPLETS_SCORE = 2500

SINGLE_SCORES = {1: 100, 5: 50}
_OF_A_KIND_MULTIPLIER = {3: 1, 4: 2, 5: 4, 6: 8}


def triple_value(face: int) -> int:
    """Base three-of-a-kind value for a face (before the 4/5/6-of-a-kind multiplier)."""
    return 1000 if face == 1 else face * 100


def _default_decomposition(counts: Counter) -> tuple[int, int]:
    """Scores each face independently.

    For any face rolled 3+ times, using *all* of those dice as a single N-of-a-kind
    is always at least as good as splitting some off as singles: the per-die bonus
    for 4/5/6-of-a-kind multiplies the triple value (x2/x4/x8), which outgrows any
    linear combination of smaller groups. So there's no subset search needed: just
    take the biggest group per face.
    """
    score = 0
    dice_used = 0
    for face, count in counts.items():
        if count >= 3:
            score += triple_value(face) * _OF_A_KIND_MULTIPLIER[count]
            dice_used += count
        elif face in SINGLE_SCORES:
            score += SINGLE_SCORES[face] * count
            dice_used += count
    return score, dice_used


def best_score(dice: tuple[int, ...]) -> tuple[int, int]:
    """Returns (score, dice_used) for the highest-scoring reading of a roll.

    dice_used == 0 means a Farkle (no scoring dice at all; the turn busts).
    dice_used == len(dice) means every die scored ("hot dice": a fresh six
    dice may be rolled next if the player continues).
    """
    counts = Counter(dice)
    best = _default_decomposition(counts)

    if len(dice) == 6:
        if len(counts) == 6 and STRAIGHT_SCORE > best[0]:
            best = (STRAIGHT_SCORE, 6)
        elif len(counts) == 3 and all(c == 2 for c in counts.values()) and THREE_PAIRS_SCORE > best[0]:
            best = (THREE_PAIRS_SCORE, 6)
        elif (
            ENABLE_TWO_TRIPLETS_BONUS
            and len(counts) == 2
            and all(c == 3 for c in counts.values())
            and TWO_TRIPLETS_SCORE > best[0]
        ):
            best = (TWO_TRIPLETS_SCORE, 6)

    return best
