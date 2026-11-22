"""Runs the full analysis and writes web/data.js for the visualization page.

Usage:
    python export_web.py                # full precision (takes ~4-5 min)
    python export_web.py --fast          # lower trial counts, for quick iteration
"""

from __future__ import annotations

import argparse
import json
import random
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from farkle.holdback import optimize_full_policy
from farkle.optimize import optimize_thresholds
from farkle.policy import ThresholdPolicy
from farkle.simulate import ev_of_reroll_with_stderr, mean_turn_score
from farkle.stats import bust_probability, expected_score_per_roll

GRID_MAX_SCORE = 4000
GRID_STEP = 100

# Kept only as an intermediate comparison point: locks just the single most
# valuable loose die on a fresh six-dice roll, but (unlike the full table)
# doesn't address smaller reroll sizes at all. See README.
SIX_ROLL_HOLD_BACK_MAX_LOOSE = 4


def _grid_point(args: tuple[int, int, dict[int, int], dict, int, int]) -> dict:
    dice_remaining, turn_score, thresholds, hold_back_table, n_trials, seed = args
    policy = ThresholdPolicy(thresholds, hold_back_table=hold_back_table)
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
            jobs.append((dice_remaining, turn_score, policy.thresholds, policy.hold_back_table, n_trials, seed))
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


def hold_back_table_to_json(table: dict[tuple[int, int, int], int]) -> list[dict]:
    rows = []
    for (total_dice, ones, fives), lock_count in sorted(table.items()):
        loose_total = ones + fives
        rows.append(
            {
                "totalDice": total_dice,
                "looseOnes": ones,
                "looseFives": fives,
                "looseTotal": loose_total,
                "lockCount": lock_count,
                "holdsBack": lock_count < loose_total,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Lower trial counts for quick iteration")
    args = parser.parse_args()

    threshold_trials = 5_000 if args.fast else 50_000
    threshold_rounds = 2 if args.fast else 6
    table_trials = 5_000 if args.fast else 80_000
    outer_rounds = 1 if args.fast else 3
    grid_trials = 1_000 if args.fast else 6_000
    summary_trials = 20_000 if args.fast else 400_000

    t0 = time.time()
    print("Optimizing the full policy (bank thresholds + which-dice-to-save table)...")
    policy = optimize_full_policy(
        threshold_trials=threshold_trials,
        threshold_rounds=threshold_rounds,
        table_trials=table_trials,
        outer_rounds=outer_rounds,
    )
    print(f"  thresholds: {policy.thresholds}  ({time.time() - t0:.1f}s)")
    print(f"  table entries: {len(policy.hold_back_table)}")

    print("Optimizing comparison baselines...")
    always_max_policy = optimize_thresholds(n_trials=threshold_trials, rounds=threshold_rounds)
    six_roll_only_policy = optimize_thresholds(
        n_trials=threshold_trials, rounds=threshold_rounds, six_roll_hold_back_max_loose=SIX_ROLL_HOLD_BACK_MAX_LOOSE
    )
    naive_hold_back_policy = optimize_thresholds(n_trials=threshold_trials, rounds=threshold_rounds, hold_back_target=2)
    print(f"  done ({time.time() - t0:.1f}s)")

    with ProcessPoolExecutor() as executor:
        t1 = time.time()
        print(f"Building decision grid ({grid_trials:,} trials/point)...")
        grid = build_decision_grid(policy, grid_trials, executor)
        print(f"  {len(grid)} grid points ({time.time() - t1:.1f}s)")

        t2 = time.time()
        print(f"Comparing strategies ({summary_trials:,} trials each)...")
        strategy_policies = {
            "Optimal (full table)": policy,
            "Six-roll hold-back only": six_roll_only_policy,
            "Always take max (no hold-back)": always_max_policy,
            "Flat threshold 300": ThresholdPolicy({d: 300 for d in range(1, 7)}),
            "Bank ASAP (threshold 1)": ThresholdPolicy({d: 1 for d in range(1, 7)}),
            "Naive uniform hold-back (target=2)": naive_hold_back_policy,
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
            "thresholdTrials": threshold_trials,
            "thresholdRounds": threshold_rounds,
            "tableTrials": table_trials,
            "outerRounds": outer_rounds,
            "gridTrials": grid_trials,
            "summaryTrials": summary_trials,
        },
        "optimalThresholds": policy.as_dict(),
        "holdBackTable": hold_back_table_to_json(policy.hold_back_table),
        "exactStats": exact_stats,
        "decisionGrid": grid,
        "strategyComparison": strategy_results,
    }

    out_path = Path(__file__).parent / "web" / "data.js"
    out_path.write_text("window.FARKLE_DATA = " + json.dumps(data, indent=2) + ";\n", encoding="utf-8")
    print(f"\nWrote {out_path} ({time.time() - t0:.1f}s total)")


if __name__ == "__main__":
    main()
