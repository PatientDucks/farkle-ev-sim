import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from farkle.rules import best_score  # noqa: E402


class TestBestScore(unittest.TestCase):
    def test_farkle_no_scoring_dice(self):
        self.assertEqual(best_score((2, 2, 3, 4, 6, 6)), (0, 0))

    def test_single_one(self):
        self.assertEqual(best_score((1,)), (100, 1))

    def test_single_five(self):
        self.assertEqual(best_score((5,)), (50, 1))

    def test_non_scoring_single_die(self):
        self.assertEqual(best_score((3,)), (0, 0))

    def test_two_singles(self):
        self.assertEqual(best_score((1, 5)), (150, 2))

    def test_three_of_a_kind_low(self):
        self.assertEqual(best_score((2, 2, 2)), (200, 3))

    def test_three_ones_special_value(self):
        self.assertEqual(best_score((1, 1, 1)), (1000, 3))

    def test_four_of_a_kind_doubles_triple(self):
        self.assertEqual(best_score((5, 5, 5, 5)), (1000, 4))

    def test_five_of_a_kind_quadruples_triple(self):
        self.assertEqual(best_score((2, 2, 2, 2, 2)), (800, 5))

    def test_six_of_a_kind_octuples_triple(self):
        self.assertEqual(best_score((1, 1, 1, 1, 1, 1)), (8000, 6))

    def test_triple_plus_extra_singles(self):
        # three 2s (200) + a 1 (100) + a 5 (50); the lone non-scoring 6 is left out
        score, used = best_score((2, 2, 2, 1, 5, 6))
        self.assertEqual(score, 350)
        self.assertEqual(used, 5)

    def test_straight(self):
        self.assertEqual(best_score((1, 2, 3, 4, 5, 6)), (1500, 6))

    def test_three_pairs(self):
        self.assertEqual(best_score((2, 2, 3, 3, 4, 4)), (1500, 6))

    def test_three_pairs_beats_default_decomposition(self):
        # 1,1,5,5,6,6 as singles would only be 100+100+50+50=300; three-pairs wins.
        self.assertEqual(best_score((1, 1, 5, 5, 6, 6)), (1500, 6))

    def test_two_triplets_bonus(self):
        # three 2s (200) + three 5s (500) = 700 by default; the bonus combo beats it.
        self.assertEqual(best_score((2, 2, 2, 5, 5, 5)), (2500, 6))

    def test_four_of_a_kind_plus_pair_not_mistaken_for_special_combo(self):
        # four 3s (doubled triple = 600) + two 5s (100) = 700; not a special 6-dice pattern.
        self.assertEqual(best_score((3, 3, 3, 3, 5, 5)), (700, 6))

    def test_partial_reroll_subset_scores_independently_of_full_roll(self):
        # Rerolling just 2 dice should never trigger whole-roll special combos.
        self.assertEqual(best_score((2, 2)), (0, 0))


if __name__ == "__main__":
    unittest.main()
