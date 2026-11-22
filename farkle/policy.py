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

from dataclasses import dataclass, field

from .rules import RollDecomposition


@dataclass
class ThresholdPolicy:
    # Indexed by dice_remaining (1..6). Reroll while turn_score < thresholds[dice_remaining].
    thresholds: dict[int, int]

    # The full, per-state answer to "how many loose dice to lock in": keyed by
    # (total_dice_this_roll, loose_ones, loose_fives), value = how many to lock
    # (locking 1s before 5s). Only consulted when nothing formed a 3+-of-a-kind
    # group this roll (see RollDecomposition). Built by holdback.py, which
    # evaluates every reachable state directly rather than applying one rule
    # everywhere; see README for why the right answer varies by state. States
    # not present in the table fall back to the simpler mechanisms below, so a
    # partially-filled table (or none at all) still behaves sensibly.
    hold_back_table: dict[tuple[int, int, int], int] = field(default_factory=dict)

    # A narrower, hand-written version of the same idea, scoped to exactly one
    # scenario: the roll is a full six dice (the start of a turn, or right
    # after hot dice), nothing formed a group, and the loose 1s/5s count is at
    # most this. In that case, lock only the single most valuable loose die.
    # Superseded by hold_back_table when a state is present there; kept as a
    # fallback and as its own comparison point in the strategy table. 0 disables it.
    six_roll_hold_back_max_loose: int = 0

    # The simplest, naive version: decline the cheapest loose dice whenever
    # locking everything would leave fewer than this many dice behind, at any
    # roll size. Kept only as a "what if you did this everywhere" baseline for
    # comparison; see README for why it's worse than the two options above.
    hold_back_target: int = 0

    def should_reroll(self, turn_score: int, dice_remaining: int) -> bool:
        return turn_score < self.thresholds[dice_remaining]

    def resolve_roll(self, d: RollDecomposition, total_dice: int) -> tuple[int, int]:
        """Returns (locked_score, dice_used) for this roll under this policy."""
        if d.special_dice_used:
            return d.special_score, d.special_dice_used
        if d.is_farkle:
            return 0, 0

        loose_total = d.loose_ones + d.loose_fives
        dice_remaining_if_all_locked = total_dice - d.forced_dice_used - loose_total
        max_declinable = loose_total - 1 if d.forced_dice_used == 0 else loose_total

        decline = 0
        if dice_remaining_if_all_locked > 0 and d.forced_dice_used == 0 and loose_total > 0:
            # Never decline a die that would otherwise complete hot dice.
            key = (total_dice, d.loose_ones, d.loose_fives)
            if key in self.hold_back_table:
                lock_count = max(1, min(loose_total, self.hold_back_table[key]))
                decline = loose_total - lock_count
            elif total_dice == 6 and loose_total <= self.six_roll_hold_back_max_loose:
                decline = max_declinable  # keep only the single most valuable loose die
            else:
                wanted_decline = max(0, self.hold_back_target - dice_remaining_if_all_locked)
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
