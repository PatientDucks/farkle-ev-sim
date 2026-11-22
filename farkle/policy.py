"""Decision policy for the reroll-vs-bank choice.

A ThresholdPolicy is the standard family of Farkle strategies: "keep rolling
until my turn score reaches at least threshold[dice_remaining], then bank."
It's simple, well understood, and turns out to approximate the EV-optimal
policy closely in practice. The optimizer in optimize.py searches for the
best threshold per dice_remaining via Monte Carlo evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThresholdPolicy:
    # Indexed by dice_remaining (1..6). Reroll while turn_score < thresholds[dice_remaining].
    thresholds: dict[int, int]

    def should_reroll(self, turn_score: int, dice_remaining: int) -> bool:
        return turn_score < self.thresholds[dice_remaining]

    def as_dict(self) -> dict[str, int]:
        return {str(k): v for k, v in sorted(self.thresholds.items())}


DEFAULT_POLICY = ThresholdPolicy(thresholds={1: 350, 2: 300, 3: 300, 4: 250, 5: 200, 6: 150})
