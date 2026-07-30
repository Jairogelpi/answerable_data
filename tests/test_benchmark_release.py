from __future__ import annotations

import unittest

from answerable.benchmark import BenchmarkCase, BenchmarkObservation, BenchmarkRunner

FR_BENCH_001 = "FR-BENCH-001"
FR_BENCH_002 = "FR-BENCH-002"
FR_BENCH_003 = "FR-BENCH-003"


class BenchmarkReleaseTests(unittest.TestCase):
    def test_phase_18_release_requires_accuracy_recall_and_zero_causal_violations(self) -> None:
        case = BenchmarkCase(
            "c1",
            "causal_identification",
            "FUNDAMENTALLY_UNIDENTIFIABLE",
            frozenset({"no_control"}),
            True,
        )
        report = BenchmarkRunner().evaluate(
            (case,),
            (
                BenchmarkObservation(
                    "c1", "FUNDAMENTALLY_UNIDENTIFIABLE", frozenset({"no_control"})
                ),
            ),
            require_full_families=False,
        )
        self.assertTrue(report.release_pass)
        unsafe = BenchmarkRunner().evaluate(
            (case,),
            (BenchmarkObservation("c1", "ANSWERABLE", frozenset(), True),),
            require_full_families=False,
        )
        self.assertFalse(unsafe.release_pass)
        self.assertEqual(unsafe.causal_safety_violations, 1)

    def test_phase_18_rejects_misaligned_or_incomplete_benchmark(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkRunner().evaluate((), ())
        case = BenchmarkCase("c1", "schema_grain", "ANSWERABLE", frozenset())
        with self.assertRaises(ValueError):
            BenchmarkRunner().evaluate(
                (case,), (BenchmarkObservation("c1", "ANSWERABLE", frozenset()),)
            )


if __name__ == "__main__":
    unittest.main()
