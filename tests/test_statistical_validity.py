from __future__ import annotations

import unittest

from answerable.statistics import CorrectionMethod, StatisticalAssessor

FR_STAT_001 = "FR-STAT-001"
FR_STAT_002 = "FR-STAT-002"
FR_STAT_003 = "FR-STAT-003"
FR_STAT_004 = "FR-STAT-004"
FR_STAT_005 = "FR-STAT-005"


class StatisticalValidityTests(unittest.TestCase):
    def test_phase_10_reports_uncertainty_effect_power_and_mde(self) -> None:
        result = StatisticalAssessor().assess_mean_difference((10, 11, 12, 13, 14), (1, 2, 3, 4, 5))
        self.assertEqual(result.estimate, 9)
        self.assertLess(result.confidence_interval[0], result.estimate)
        self.assertGreater(result.effect_size, 1)
        self.assertGreater(result.power, 0.8)
        self.assertGreater(result.minimum_detectable_effect, 0)

    def test_phase_10_underpowered_null_forbids_no_effect_claim(self) -> None:
        result = StatisticalAssessor().assess_mean_difference((1, 2), (1, 2))
        self.assertIn("insufficient_power", {item.code for item in result.findings})
        self.assertEqual(result.p_value, 1)
        self.assertIn("no effect", result.forbidden_claims[0])

    def test_phase_10_multiple_comparison_corrections_are_bounded(self) -> None:
        p_values = (0.01, 0.04, 0.2)
        bonferroni = StatisticalAssessor.adjust_p_values(p_values, CorrectionMethod.BONFERRONI)
        bh = StatisticalAssessor.adjust_p_values(p_values, CorrectionMethod.BENJAMINI_HOCHBERG)
        for observed, expected in zip(bonferroni, (0.03, 0.12, 0.6), strict=True):
            self.assertAlmostEqual(observed, expected)
        self.assertTrue(all(0 <= value <= 1 for value in bh))
        with self.assertRaises(ValueError):
            StatisticalAssessor.adjust_p_values((), CorrectionMethod.BONFERRONI)

    def test_phase_10_checks_influence_subgroups_and_robust_alternative(self) -> None:
        findings = StatisticalAssessor.assumption_findings(
            influential_fraction=0.1,
            subgroup_effects=(-1, 2),
            robust_estimate=1,
            classical_estimate=10,
        )
        self.assertEqual(
            {item.code for item in findings},
            {"influential_observations", "subgroup_instability", "robustness_failure"},
        )

    def test_phase_10_rejects_invalid_design_parameters(self) -> None:
        with self.assertRaises(ValueError):
            StatisticalAssessor().assess_mean_difference((1,), (1, 2))
        with self.assertRaises(ValueError):
            StatisticalAssessor().assess_mean_difference((1, 2), (1, 2), alpha=2)


if __name__ == "__main__":
    unittest.main()
