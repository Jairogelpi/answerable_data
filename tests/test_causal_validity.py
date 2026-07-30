from __future__ import annotations

import unittest

from answerable.causal import CausalContract, CausalIdentifier, IdentificationStrategy

FR_CAUSAL_001 = "FR-CAUSAL-001"
FR_CAUSAL_002 = "FR-CAUSAL-002"
FR_CAUSAL_003 = "FR-CAUSAL-003"
FR_CAUSAL_004 = "FR-CAUSAL-004"
FR_CAUSAL_005 = "FR-CAUSAL-005"


class CountingEstimator:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, contract: CausalContract) -> float:
        self.calls += 1
        return 2.5


class CausalValidityTests(unittest.TestCase):
    def contract(self, strategy: IdentificationStrategy) -> CausalContract:
        return CausalContract(
            treatment="campaign",
            outcome="revenue",
            population="eligible customers",
            estimand="ATE",
            strategy=strategy,
            adjustment_set=frozenset({"prior_revenue"}),
            assumptions=("consistency", "positivity"),
            falsification_checks=("placebo outcome",),
            sensitivity_checks=("E-value",),
        )

    def test_phase_11_identification_failure_prevents_estimation(self) -> None:
        estimator = CountingEstimator()
        assessment = CausalIdentifier().assess(
            self.contract(IdentificationStrategy.REGRESSION), estimator
        )
        self.assertFalse(assessment.identified)
        self.assertIsNone(assessment.estimate)
        self.assertEqual(estimator.calls, 0)
        self.assertIn("caused", assessment.forbidden_claims)

    def test_phase_11_identifies_supported_strategies_then_estimates(self) -> None:
        cases = (
            (IdentificationStrategy.RANDOMIZED, {"randomization_valid": True}),
            (IdentificationStrategy.REGRESSION, {"exchangeability_supported": True}),
            (
                IdentificationStrategy.DIFFERENCE_IN_DIFFERENCES,
                {"parallel_trends_supported": True},
            ),
            (
                IdentificationStrategy.INSTRUMENTAL_VARIABLE,
                {"instrument_valid": True},
            ),
            (
                IdentificationStrategy.REGRESSION_DISCONTINUITY,
                {"discontinuity_valid": True},
            ),
        )
        for strategy, evidence in cases:
            with self.subTest(strategy=strategy):
                estimator = CountingEstimator()
                assessment = CausalIdentifier().assess(
                    self.contract(strategy), estimator, **evidence
                )
                self.assertTrue(assessment.identified)
                self.assertEqual(assessment.estimate, 2.5)
                self.assertEqual(estimator.calls, 1)

    def test_phase_11_requires_sensitivity_and_preserves_refutations(self) -> None:
        contract = CausalContract(
            "treatment",
            "outcome",
            "population",
            "ATE",
            IdentificationStrategy.RANDOMIZED,
            falsification_checks=("placebo",),
        )
        assessment = CausalIdentifier().assess(
            contract, CountingEstimator(), randomization_valid=True
        )
        self.assertEqual(assessment.refutations, ("placebo",))
        self.assertIn("missing_sensitivity", {item.code for item in assessment.findings})

    def test_phase_11_validates_causal_contract(self) -> None:
        with self.assertRaises(ValueError):
            CausalContract("", "outcome", "population", "ATE", IdentificationStrategy.RANDOMIZED)
        with self.assertRaises(ValueError):
            CausalContract("x", "x", "population", "ATE", IdentificationStrategy.RANDOMIZED)


if __name__ == "__main__":
    unittest.main()
