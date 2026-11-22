"""Runs the full analysis and writes web/data.js for the visualization page.

Usage:
    python export_web.py                # full precision (takes ~1-2 minutes)
    python export_web.py --fast          # lower trial counts, for quick iteration
"""

from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from farkle.optimize import optimize_thresholds
from farkle.policy import ThresholdPolicy
from farkle.simulate import ev_of_reroll_with_stderr, mean_turn_score
from farkle.stats import bust_probability, expected_score_per_roll

GRID_MAX_SCORE = 4000
GRID_STEP = 100


def _grid_point(args: tuple[int, int, dict[int, int], int, int]) -> dict:
    dice_remaining, turn_score, thresholds, n_trials, seed = args
    policy = ThresholdPolicy(thresholds)
    rng = random.Random(seed)
    ev_reroll, stderr = ev_of_reroll_with_stderr(turn_score, dice_remaining, policy, n_trials, rng)
    return {
        "diceRemaining": dice_remaining,
        "turnScore": turn_score,
        "evBank": turn_score,
        "evReroll": round(ev_reroll, 1),
        "stderr": round(stderr, 2),
        "rerollBetter": ev_reroll > turn_score,
    }


def build_decision_grid(policy: ThresholdPolicy, n_trials: int, executor: ProcessPoolExecutor) -> list[dict]:
    jobs = []
    seed = 1000
    for dice_remaining in range(1, 7):
        for turn_score in range(0, GRID_MAX_SCORE + 1, GRID_STEP):
            jobs.append((dice_remaining, turn_score, policy.thresholds, n_trials, seed))
            seed += 1
    return list(executor.map(_grid_point, jobs))


def build_exact_stats() -> list[dict]:
    return [
        {
            "diceRemaining": d,
            "bustProbability": round(bust_probability(d), 5),
            "expectedScorePerRoll": round(expected_score_per_roll(d), 1),
        }
        for d in range(1, 7)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Lower trial counts for quick iteration")
    args = parser.parse_args()

    optimize_trials = 8_000 if args.fast else 60_000
    optimize_rounds = 3 if args.fast else 6
    grid_trials = 1_000 if args.fast else 6_000
    summary_trials = 20_000 if args.fast else 300_000

    t0 = time.time()
    print(f"Optimizing thresholds ({optimize_trials:,} trials/eval, {optimize_rounds} rounds)...")
    policy = optimize_thresholds(n_trials=optimize_trials, rounds=optimize_rounds)
    print(f"  thresholds: {policy.thresholds}  ({time.time() - t0:.1f}s)")

    print("Optimizing a 'hold back loose singles' policy for comparison (hold_back_target=2)...")
    hold_back_policy = optimize_thresholds(n_trials=optimize_trials, rounds=optimize_rounds, hold_back_target=2)
    print(f"  thresholds: {hold_back_policy.thresholds}  ({time.time() - t0:.1f}s)")

    with ProcessPoolExecutor() as executor:
        t1 = time.time()
        print(f"Building decision grid ({grid_trials:,} trials/point)...")
        grid = build_decision_grid(policy, grid_trials, executor)
        print(f"  {len(grid)} grid points ({time.time() - t1:.1f}s)")

        t2 = time.time()
        print(f"Comparing strategies ({summary_trials:,} trials each)...")
        strategy_policies = {
            "Optimal (this sim)": policy,
            "Flat threshold 300": ThresholdPolicy({d: 300 for d in range(1, 7)}),
            "Bank ASAP (threshold 1)": ThresholdPolicy({d: 1 for d in range(1, 7)}),
            "Hold back loose singles (target=2)": hold_back_policy,
        }
        strategy_results = []
        for name, strat_policy in strategy_policies.items():
            rng = random.Random(hash(name) & 0xFFFFFFFF)
            ev = mean_turn_score(strat_policy, summary_trials, rng)
            strategy_results.append({"name": name, "meanTurnScore": round(ev, 1), "thresholds": strat_policy.as_dict()})
        print(f"  done ({time.time() - t2:.1f}s)")

    exact_stats = build_exact_stats()

    data = {
        "generatedAtTrials": {
            "optimizeTrials": optimize_trials,
            "optimizeRounds": optimize_rounds,
            "gridTrials": grid_trials,
            "summaryTrials": summary_trials,
        },
        "optimalThresholds": policy.as_dict(),
        "exactStats": exact_stats,
        "decisionGrid": grid,
        "strategyComparison": strategy_results,
    }

    out_path = Path(__file__).parent / "web" / "data.js"
    out_path.write_text("window.FARKLE_DATA = " + json.dumps(data, indent=2) + ";\n", encoding="utf-8")
    print(f"\nWrote {out_path} ({time.time() - t0:.1f}s total)")


if __name__ == "__main__":
    main()
