from __future__ import annotations

import unittest

from answerable.statistics import ExperimentAssessor, ExperimentDesign

FR_EXPERIMENT_001 = "FR-EXPERIMENT-001"
FR_EXPERIMENT_002 = "FR-EXPERIMENT-002"
FR_EXPERIMENT_003 = "FR-EXPERIMENT-003"
FR_EXPERIMENT_004 = "FR-EXPERIMENT-004"
FR_EXPERIMENT_005 = "FR-EXPERIMENT-005"


class ExperimentValidityTests(unittest.TestCase):
    def test_phase_10_valid_experiment_has_no_findings(self) -> None:
        design = ExperimentDesign((0.5, 0.5), "customer", "customer")
        self.assertEqual(ExperimentAssessor().assess((500, 500), design=design), ())

    def test_phase_10_detects_srm_exposure_contamination_and_attrition(self) -> None:
        findings = ExperimentAssessor().assess(
            (900, 100),
            design=ExperimentDesign((0.5, 0.5), "customer", "customer"),
            exposure_rate=0.8,
            contamination_rate=0.1,
            attrition_rates=(0.01, 0.1),
            balance_differences=(0.2,),
            guardrails_pass=False,
        )
        self.assertEqual(
            {item.code for item in findings},
            {
                "sample_ratio_mismatch",
                "missing_exposure",
                "contamination",
                "differential_attrition",
                "pre_experiment_imbalance",
                "guardrail_failure",
            },
        )

    def test_phase_10_blocks_undeclared_sequential_testing_and_unit_mismatch(self) -> None:
        design = ExperimentDesign(
            (0.5, 0.5),
            "household",
            "user",
            planned_looks=1,
            current_look=2,
            stopping_rule_declared=False,
        )
        findings = ExperimentAssessor().assess((50, 50), design=design)
        self.assertEqual(
            {item.code for item in findings},
            {"invalid_sequential_testing", "randomization_unit_mismatch"},
        )

    def test_phase_10_validates_allocation_contract(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentAssessor().assess((1,), design=ExperimentDesign((0.5, 0.5), "user", "user"))
        with self.assertRaises(ValueError):
            ExperimentAssessor().assess((1, 1), design=ExperimentDesign((0.4, 0.4), "user", "user"))


if __name__ == "__main__":
    unittest.main()
