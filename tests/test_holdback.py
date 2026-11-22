import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from farkle.holdback import reachable_states  # noqa: E402


class TestReachableStates(unittest.TestCase):
    def test_count_matches_manual_enumeration(self):
        states = reachable_states()
        expected = [
            (total_dice, ones, fives)
            for total_dice in range(1, 7)
            for ones in range(3)
            for fives in range(3)
            if 0 < ones + fives <= total_dice
        ]
        self.assertEqual(sorted(states), sorted(expected))
        self.assertEqual(len(states), 38)

    def test_no_state_exceeds_its_own_dice_count(self):
        for total_dice, ones, fives in reachable_states():
            self.assertLessEqual(ones + fives, total_dice)

    def test_every_state_has_at_least_one_loose_die(self):
        for total_dice, ones, fives in reachable_states():
            self.assertGreater(ones + fives, 0)

    def test_loose_counts_never_exceed_two(self):
        # 3+ of a face forms a group instead of staying "loose".
        for _total_dice, ones, fives in reachable_states():
            self.assertLessEqual(ones, 2)
            self.assertLessEqual(fives, 2)

    def test_one_die_rolls_only_allow_a_single_loose_die(self):
        one_die_states = [s for s in reachable_states() if s[0] == 1]
        self.assertEqual(sorted(one_die_states), [(1, 0, 1), (1, 1, 0)])


if __name__ == "__main__":
    unittest.main()
