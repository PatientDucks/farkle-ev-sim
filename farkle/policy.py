"""Decision policy for Farkle: the reroll-vs-bank choice, and the "hold back"
choice of how many loose scoring dice to actually lock in versus leave for
the next roll.

A ThresholdPolicy is the standard family of Farkle strategies: "keep rolling
until my turn score reaches at least threshold[dice_remaining], then bank."
It's simple, well understood, and turns out to approximate the EV-optimal
policy closely in practice. The optimizer in optimize.py searches for the
best threshold per dice_remaining via Monte Carlo evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rules import RollDecomposition


@dataclass
class ThresholdPolicy:
    # Indexed by dice_remaining (1..6). Reroll while turn_score < thresholds[dice_remaining].
    thresholds: dict[int, int]

    # 3+-of-a-kind groups and special combos are always locked in full if rolled
    # (see RollDecomposition). Loose 1s and 5s are the real choice: lock them all
    # (the default, hold_back_target=0), or decline the cheapest ones to keep
    # dice_remaining at least this high, betting on a safer next roll instead of
    # the guaranteed points. At least one scoring die is always locked if the
    # roll scored anything at all.
    hold_back_target: int = 0

    def should_reroll(self, turn_score: int, dice_remaining: int) -> bool:
        return turn_score < self.thresholds[dice_remaining]

    def resolve_roll(self, d: RollDecomposition, total_dice: int) -> tuple[int, int]:
        """Returns (locked_score, dice_used) for this roll under this policy."""
        if d.special_dice_used:
            return d.special_score, d.special_dice_used
        if d.is_farkle:
            return 0, 0

        dice_remaining_if_all_locked = total_dice - d.forced_dice_used - d.loose_ones - d.loose_fives
        wanted_decline = max(0, self.hold_back_target - dice_remaining_if_all_locked)
        max_declinable = d.loose_ones + d.loose_fives
        if d.forced_dice_used == 0:
            max_declinable -= 1  # must lock at least one single if nothing else scored
        decline = min(wanted_decline, max(0, max_declinable))

        decline_fives = min(decline, d.loose_fives)  # decline the cheaper dice first
        decline_ones = decline - decline_fives

        locked_ones = d.loose_ones - decline_ones
        locked_fives = d.loose_fives - decline_fives
        locked_score = d.forced_score + locked_ones * 100 + locked_fives * 50
        dice_used = d.forced_dice_used + locked_ones + locked_fives
        return locked_score, dice_used

    def as_dict(self) -> dict[str, int]:
        return {str(k): v for k, v in sorted(self.thresholds.items())}


DEFAULT_POLICY = ThresholdPolicy(thresholds={1: 350, 2: 300, 3: 300, 4: 250, 5: 200, 6: 150})
