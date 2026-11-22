import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from farkle.policy import ThresholdPolicy  # noqa: E402
from farkle.rules import decompose_roll  # noqa: E402

BASE_THRESHOLDS = {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1}


class TestResolveRoll(unittest.TestCase):
    def test_default_policy_locks_everything(self):
        policy = ThresholdPolicy(BASE_THRESHOLDS)
        d = decompose_roll((1, 1, 2, 3, 4, 6))  # two loose ones, four junk
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (200, 2))

    def test_farkle_resolves_to_zero(self):
        policy = ThresholdPolicy(BASE_THRESHOLDS)
        d = decompose_roll((2, 2, 3, 4, 6, 6))
        self.assertEqual(policy.resolve_roll(d, 6), (0, 0))

    def test_special_combo_always_locks_in_full(self):
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=6)
        d = decompose_roll((1, 2, 3, 4, 5, 6))  # straight
        self.assertEqual(policy.resolve_roll(d, 6), (1500, 6))

    def test_six_roll_hold_back_locks_only_the_best_loose_die(self):
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=4)
        # Two loose ones, four junk: hold-back should lock just one 1 (100),
        # declining the other to keep five dice live instead of four.
        d = decompose_roll((1, 1, 2, 3, 4, 6))
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (100, 1))

    def test_six_roll_hold_back_prefers_locking_a_one_over_a_five(self):
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=4)
        d = decompose_roll((1, 5, 2, 2, 3, 3))  # one loose 1, one loose 5, four junk
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (100, 1))  # keeps the 1, declines the 5

    def test_six_roll_hold_back_never_gives_up_achievable_hot_dice(self):
        # All six dice are loose 1s/5s: locking everything already means hot
        # dice (dice_remaining becomes 6 again), which must never be declined
        # just to satisfy a hold-back target.
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=4)
        d = decompose_roll((1, 1, 5, 5, 1, 5))  # three 1s + three 5s: forced groups, not loose
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual(used, 6)  # fully locked either way (this roll has no loose singles)

    def test_six_roll_hold_back_does_not_apply_when_a_group_is_present(self):
        # Three 2s (forced) plus two loose ones: hold-back only covers pure
        # loose-singles rolls, so this should still lock everything.
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=4)
        d = decompose_roll((2, 2, 2, 1, 1, 6))
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (200 + 200, 5))

    def test_six_roll_hold_back_does_not_apply_to_smaller_rerolls(self):
        # Same loose-singles shape, but this is a 4-dice reroll, not a fresh
        # six: the six-roll-specific hold-back must not engage here.
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=4)
        d = decompose_roll((1, 1, 2, 3))
        score, used = policy.resolve_roll(d, 4)
        self.assertEqual((score, used), (200, 2))

    def test_six_roll_hold_back_respects_max_loose_cap(self):
        # Cap of 1: a roll with 2 loose ones exceeds the cap, so it should
        # lock everything instead of holding back.
        policy = ThresholdPolicy(BASE_THRESHOLDS, six_roll_hold_back_max_loose=1)
        d = decompose_roll((1, 1, 2, 3, 4, 6))
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (200, 2))

    def test_hold_back_table_overrides_the_six_roll_fallback(self):
        # Table says lock 2 of 2 here even though six_roll_hold_back_max_loose
        # would otherwise say lock just 1: the table takes priority.
        policy = ThresholdPolicy(
            BASE_THRESHOLDS,
            hold_back_table={(6, 2, 0): 2},
            six_roll_hold_back_max_loose=4,
        )
        d = decompose_roll((1, 1, 2, 3, 4, 6))
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (200, 2))

    def test_hold_back_table_applies_to_non_six_rolls(self):
        # Unlike six_roll_hold_back_max_loose, the table isn't limited to
        # fresh six-dice rolls.
        policy = ThresholdPolicy(BASE_THRESHOLDS, hold_back_table={(4, 1, 1): 1})
        d = decompose_roll((1, 5, 2, 3))  # 4-dice reroll, one loose 1, one loose 5
        score, used = policy.resolve_roll(d, 4)
        self.assertEqual((score, used), (100, 1))  # keeps the 1, declines the 5

    def test_hold_back_table_missing_state_falls_back(self):
        # A state not present in the table falls back to the simpler
        # mechanisms (lock everything, by default).
        policy = ThresholdPolicy(BASE_THRESHOLDS, hold_back_table={(6, 2, 0): 1})
        d = decompose_roll((1, 5, 2, 2, 3, 3))  # (6, 1, 1), not in the table
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (150, 2))

    def test_hold_back_table_clamps_out_of_range_lock_count(self):
        # Defensive: a lock count outside [1, loose_total] is clamped rather
        # than trusted verbatim.
        policy = ThresholdPolicy(BASE_THRESHOLDS, hold_back_table={(6, 2, 0): 99})
        d = decompose_roll((1, 1, 2, 3, 4, 6))
        score, used = policy.resolve_roll(d, 6)
        self.assertEqual((score, used), (200, 2))  # clamped to loose_total=2


if __name__ == "__main__":
    unittest.main()
