"""Builds the full "which dice to save" table: for every reachable
(total_dice_this_roll, loose_ones, loose_fives) state with no 3+-of-a-kind
group, finds the number of loose dice to lock in that maximizes the EV of
optimal play from there.

This generalizes the six-dice-only finding (always lock just one loose die)
to every roll size, state by state, by direct Monte Carlo comparison rather
than assuming one rule applies everywhere.

The table and the bank thresholds are interdependent (a better table changes
the value of being at every dice-remaining state, which shifts the optimal
thresholds; new thresholds change which states get reached, which can shift
the table), so optimize_full_policy iterates both together until they
stabilize, the same Jacobi-iteration approach already used for the thresholds
alone.
"""

from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor

from .optimize import optimize_thresholds
from .policy import ThresholdPolicy
from .simulate import state_value

HoldBackTable = dict[tuple[int, int, int], int]


def reachable_states() -> list[tuple[int, int, int]]:
    """Every (total_dice, loose_ones, loose_fives) combo where a lock-count
    decision actually exists. loose_ones/loose_fives are capped at 2 each:
    three or more of a face forms a group instead of staying "loose"."""
    states = []
    for total_dice in range(1, 7):
        for ones in range(3):
            for fives in range(3):
                loose_total = ones + fives
                if 0 < loose_total <= total_dice:
                    states.append((total_dice, ones, fives))
    return states


def _best_lock_count(
    state: tuple[int, int, int],
    thresholds: dict[int, int],
    hold_back_table: HoldBackTable,
    n_trials: int,
    seed: int,
) -> tuple[tuple[int, int, int], int]:
    total_dice, ones, fives = state
    loose_total = ones + fives
    policy = ThresholdPolicy(thresholds, hold_back_table=hold_back_table)
    rng = random.Random(seed)

    best_lock = 1
    best_value = -1.0
    for lock_count in range(1, loose_total + 1):
        lock_ones = min(ones, lock_count)
        lock_fives = lock_count - lock_ones
        score = lock_ones * 100 + lock_fives * 50
        dice_remaining = total_dice - lock_count
        effective_dice_remaining = 6 if dice_remaining == 0 else dice_remaining  # locking everything = hot dice
        value = state_value(score, effective_dice_remaining, policy, n_trials, rng)
        if value > best_value:
            best_value = value
            best_lock = lock_count
    return state, best_lock


def build_hold_back_table(
    continuation_policy: ThresholdPolicy,
    n_trials: int = 60_000,
    seed: int = 2024,
    max_workers: int | None = None,
) -> HoldBackTable:
    """For each reachable state, finds the lock count that maximizes the EV of
    optimal play from there, using `continuation_policy` (including its own
    table) for every decision after this one."""
    states = reachable_states()
    table: HoldBackTable = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        jobs = [
            executor.submit(
                _best_lock_count,
                state,
                continuation_policy.thresholds,
                continuation_policy.hold_back_table,
                n_trials,
                seed + i,
            )
            for i, state in enumerate(states)
        ]
        for job in jobs:
            state, lock_count = job.result()
            table[state] = lock_count
    return table


def optimize_full_policy(
    threshold_trials: int = 50_000,
    threshold_rounds: int = 6,
    table_trials: int = 60_000,
    outer_rounds: int = 3,
    seed: int = 2024,
    max_workers: int | None = None,
) -> ThresholdPolicy:
    """Iterates building the hold-back table and re-optimizing the bank
    thresholds under it until both stabilize."""
    policy = optimize_thresholds(
        n_trials=threshold_trials, rounds=threshold_rounds, seed=seed, max_workers=max_workers
    )

    for round_i in range(outer_rounds):
        table = build_hold_back_table(policy, n_trials=table_trials, seed=seed + round_i * 100, max_workers=max_workers)
        policy = optimize_thresholds(
            n_trials=threshold_trials,
            rounds=threshold_rounds,
            seed=seed + round_i * 100,
            max_workers=max_workers,
            base_thresholds=policy.thresholds,
            hold_back_table=table,
        )

    return policy
