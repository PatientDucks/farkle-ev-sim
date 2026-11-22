"""Monte Carlo simulation of a single Farkle turn under a given policy."""

from __future__ import annotations

import random

from .policy import ThresholdPolicy
from .rules import decompose_roll


def simulate_from_state(
    turn_score: int,
    dice_remaining: int,
    policy: ThresholdPolicy,
    rng: random.Random,
) -> int:
    """Plays out the rest of a turn from a mid-turn state, rolling immediately
    (i.e. this models "I choose to reroll right now"), then following `policy`
    for every decision after that. Returns the final banked points for the
    whole turn (0 if it busts, which also wipes out the turn_score passed in,
    matching the real Farkle rule that a Farkle loses the entire turn).
    """
    while True:
        rolled_count = dice_remaining
        dice = tuple(rng.randint(1, 6) for _ in range(rolled_count))
        decomposition = decompose_roll(dice)
        if decomposition.is_farkle:
            return 0
        score, used = policy.resolve_roll(decomposition, rolled_count)
        turn_score += score
        dice_remaining = 6 if used == rolled_count else rolled_count - used
        if not policy.should_reroll(turn_score, dice_remaining):
            return turn_score


def simulate_turn(policy: ThresholdPolicy, rng: random.Random) -> int:
    """Plays a full turn from scratch (six fresh dice, zero turn score)."""
    return simulate_from_state(0, 6, policy, rng)


def simulate_many(policy: ThresholdPolicy, n_trials: int, rng: random.Random) -> list[int]:
    return [simulate_turn(policy, rng) for _ in range(n_trials)]


def mean_turn_score(policy: ThresholdPolicy, n_trials: int, rng: random.Random) -> float:
    total = sum(simulate_turn(policy, rng) for _ in range(n_trials))
    return total / n_trials


def ev_of_reroll(
    turn_score: int,
    dice_remaining: int,
    policy: ThresholdPolicy,
    n_trials: int,
    rng: random.Random,
) -> float:
    """Expected value of choosing to reroll from (turn_score, dice_remaining),
    then following `policy` for the rest of the turn."""
    total = sum(simulate_from_state(turn_score, dice_remaining, policy, rng) for _ in range(n_trials))
    return total / n_trials


def state_value(
    turn_score: int,
    dice_remaining: int,
    policy: ThresholdPolicy,
    n_trials: int,
    rng: random.Random,
) -> float:
    """EV of optimal play from (turn_score, dice_remaining) under `policy`:
    bank now if the policy says to, otherwise the EV of rerolling."""
    if not policy.should_reroll(turn_score, dice_remaining):
        return turn_score
    return ev_of_reroll(turn_score, dice_remaining, policy, n_trials, rng)


def ev_of_reroll_with_stderr(
    turn_score: int,
    dice_remaining: int,
    policy: ThresholdPolicy,
    n_trials: int,
    rng: random.Random,
) -> tuple[float, float]:
    """Same as ev_of_reroll, but also returns the standard error of the mean
    (sqrt(sample variance / n)), so results can be shown with a confidence band."""
    total = 0.0
    total_sq = 0.0
    for _ in range(n_trials):
        outcome = simulate_from_state(turn_score, dice_remaining, policy, rng)
        total += outcome
        total_sq += outcome * outcome
    mean = total / n_trials
    variance = max(0.0, total_sq / n_trials - mean * mean)
    stderr = (variance / n_trials) ** 0.5
    return mean, stderr
