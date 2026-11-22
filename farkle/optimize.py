"""Finds the EV-optimal bank threshold per dice_remaining.

For a fixed dice_remaining d, the optimal threshold is exactly the turn_score
at which EV(reroll) == EV(bank) == turn_score: below it, rerolling has
higher EV; above it, banking does. That's a monotonic indifference point, so
instead of a blind grid search over "mean score of the whole policy" (noisy,
and only as good as the search range you guess upfront), we binary-search
each dice_remaining's threshold directly against that condition.

The six thresholds are interdependent (e.g. the value of being at
dice_remaining=4 depends on the dice_remaining=6 threshold, since hot dice
can route you there), so this runs several rounds, each recomputing all six
thresholds in parallel against the previous round's values, Jacobi-iteration
style, until they stabilize.
"""

from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor

from .policy import DEFAULT_POLICY, ThresholdPolicy
from .simulate import ev_of_reroll

SEARCH_LO = 0.0
SEARCH_HI = 50_000.0
BISECTION_ITERS = 22


def _find_threshold(
    dice_remaining: int,
    base_thresholds: dict[int, int],
    hold_back_target: int,
    six_roll_hold_back_max_loose: int,
    n_trials: int,
    seed: int,
) -> float:
    rng = random.Random(seed)
    lo, hi = SEARCH_LO, SEARCH_HI
    for _ in range(BISECTION_ITERS):
        mid = (lo + hi) / 2
        trial_thresholds = dict(base_thresholds)
        trial_thresholds[dice_remaining] = int(round(mid))
        policy = ThresholdPolicy(
            trial_thresholds,
            hold_back_target=hold_back_target,
            six_roll_hold_back_max_loose=six_roll_hold_back_max_loose,
        )
        ev_reroll = ev_of_reroll(int(round(mid)), dice_remaining, policy, n_trials, rng)
        if ev_reroll > mid:
            lo = mid  # worth continuing even here -> true threshold is higher
        else:
            hi = mid
    return (lo + hi) / 2


def optimize_thresholds(
    n_trials: int = 40_000,
    rounds: int = 5,
    seed: int = 42,
    max_workers: int | None = None,
    hold_back_target: int = 0,
    six_roll_hold_back_max_loose: int = 0,
) -> ThresholdPolicy:
    thresholds = dict(DEFAULT_POLICY.thresholds)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for round_i in range(rounds):
            jobs = {
                d: executor.submit(
                    _find_threshold,
                    d,
                    thresholds,
                    hold_back_target,
                    six_roll_hold_back_max_loose,
                    n_trials,
                    seed + round_i * 10 + d,
                )
                for d in range(1, 7)
            }
            thresholds = {d: int(round(job.result())) for d, job in jobs.items()}

    return ThresholdPolicy(
        thresholds, hold_back_target=hold_back_target, six_roll_hold_back_max_loose=six_roll_hold_back_max_loose
    )
