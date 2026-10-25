import tempfile
import unittest
from pathlib import Path

from evallab import scorers, stats
from evallab.store import Store

FIELDS = {"phase": {"scorer": "exact"}, "enrollment": {"scorer": "number"}}


class Scoring(unittest.TestCase):
    def test_four_outcomes(self):
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], 80, 80), "correct")
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], 80, 60), "wrong")
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], 80, None), "missed")
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], None, 120), "hallucinated")
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], None, "not stated"), "correct")

    def test_phase_spellings(self):
        for got in ["2", "Phase 2", "phase II", "II", "Phase 2b"]:
            self.assertEqual(scorers.score_field(FIELDS["phase"], "2", got), "correct", got)
        for got in ["1/2", "Phase I/II", "Phase 1 and 2"]:
            self.assertEqual(scorers.score_field(FIELDS["phase"], "1/2", got), "correct", got)
        self.assertEqual(scorers.score_field(FIELDS["phase"], "2", "3"), "wrong")

    def test_numbers_written_differently(self):
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], 1200, "1,200 participants"), "correct")
        self.assertEqual(scorers.score_field(FIELDS["enrollment"], 1200, "1'200"), "correct")

    def test_missing_output(self):
        self.assertEqual(scorers.score_case(FIELDS, {"phase": "2", "enrollment": None}, None),
                         {"phase": "missed", "enrollment": "correct"})


class SuiteBuilder(unittest.TestCase):
    """Bugs found while checking the first real runs."""

    def test_combined_phases_count_as_stated(self):
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location("b", pathlib.Path(__file__).parent.parent / "scripts" / "build_registry_suite.py")
        b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
        self.assertTrue(b.phase_stated("1/2", "a dose-escalation Phase 1/2a trial"))
        self.assertTrue(b.phase_stated("1/2", "This phase I/II study"))
        self.assertTrue(b.phase_stated("2", "a randomised Phase 2b trial"))
        self.assertFalse(b.phase_stated("3", "a phase 2 study"))
        self.assertFalse(b.phase_stated("2", "Part 2 is a dose expansion"))

    def test_zero_participants_is_no_answer(self):
        spec = {"scorer": "number", "zero_is_null": True}
        self.assertEqual(scorers.score_field(spec, None, 0), "correct")
        self.assertEqual(scorers.score_field(spec, 80, 0), "missed")


class Statistics(unittest.TestCase):
    def test_identical_runs_show_no_difference(self):
        a = [True, False] * 15
        diff, low, high = stats.paired_bootstrap(a, a)
        self.assertEqual((diff, low, high), (0.0, 0.0, 0.0))
        self.assertEqual(stats.mcnemar_exact(a, a), (0, 0, 1.0))

    def test_clear_improvement(self):
        a = [False] * 20 + [True] * 10
        b = [True] * 30
        diff, low, high = stats.paired_bootstrap(a, b)
        only_a, only_b, p = stats.mcnemar_exact(a, b)
        self.assertGreater(low, 0)
        self.assertEqual((only_a, only_b), (0, 20))
        self.assertLess(p, 0.001)
        self.assertEqual(stats.verdict(diff, low, high, p), "better")

    def test_small_difference_is_not_called(self):
        a = [True] * 27 + [False] * 3
        b = [True] * 28 + [False] * 2
        diff, low, high = stats.paired_bootstrap(a, b)
        p = stats.mcnemar_exact(a, b)[2]
        self.assertEqual(stats.verdict(diff, low, high, p), "no clear difference")

    def test_mcnemar_known_value(self):
        # 1 vs 9 discordant cases: two-sided exact p = 2 * (1 + 10) / 1024
        a = [True] + [False] * 9
        b = [False] + [True] * 9
        self.assertAlmostEqual(stats.mcnemar_exact(a, b)[2], 22 / 1024)


class Storage(unittest.TestCase):
    def test_resume_skips_answered_cases(self):
        with tempfile.TemporaryDirectory() as d:
            s = Store(Path(d) / "runs.db")
            s.start_run({"id": "r1", "suite": "s", "suite_hash": "h", "model": "m", "prompt": "v1",
                         "prompt_hash": "p", "started": "t", "note": ""})
            s.save_answer("r1", "c1", {"phase": "2"}, {"phase": "correct"}, 10, 100, 20)
            s.save_answer("r1", "c2", None, {}, 10, 0, 0, error="timeout")
            self.assertEqual(s.answered("r1"), {"c1"})


if __name__ == "__main__":
    unittest.main()
