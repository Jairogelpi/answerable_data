from __future__ import annotations

import unittest

from answerable.decision import Alternative, DiagnosticAssessor, PrescriptiveAssessor
from answerable.decision.diagnostic import DriverContribution

FR_DIAG_001 = "FR-DIAG-001"
FR_DIAG_002 = "FR-DIAG-002"
FR_DIAG_003 = "FR-DIAG-003"
FR_PRESCRIPTIVE_001 = "FR-PRESCRIPTIVE-001"
FR_PRESCRIPTIVE_002 = "FR-PRESCRIPTIVE-002"


class DiagnosticAndPrescriptiveTests(unittest.TestCase):
    def test_phase_12_decomposes_contribution_without_calling_it_causal(self) -> None:
        assessment = DiagnosticAssessor().decompose(
            100,
            130,
            (
                DriverContribution("price", 10, "strong"),
                DriverContribution("volume", 15, "moderate", causal=True),
            ),
        )
        self.assertEqual(assessment.residual, 5)
        self.assertEqual(
            {item.code for item in assessment.findings},
            {"unexplained_residual", "unsupported_causal_driver"},
        )

    def test_phase_12_blocks_unverified_movement_and_detects_simpson(self) -> None:
        assessment = DiagnosticAssessor().decompose(
            10, 20, (), reconciled=False, definition_stable=False
        )
        self.assertIn("unverified_metric_movement", {item.code for item in assessment.findings})
        finding = DiagnosticAssessor.simpsons_paradox(1, (-1, -1))[0]
        self.assertEqual(finding.code, "simpsons_paradox")
        self.assertEqual(DiagnosticAssessor.simpsons_paradox(1, (1, -1)), ())

    def test_phase_12_recommendation_uses_uncertainty_guardrails_and_reversal(self) -> None:
        recommendation = PrescriptiveAssessor().recommend(
            "maximize retained revenue",
            (
                Alternative("aggressive", 100, 80),
                Alternative("balanced", 70, 10),
                Alternative("unsafe", 200, 1, guardrails_pass=False),
            ),
            constraints=("budget <= 1000",),
            downside_guardrails=("complaints <= 2%",),
            reversal_condition="Choose aggressive if its uncertainty falls below 30.",
        )
        self.assertEqual(recommendation.selected, "balanced")
        self.assertTrue(recommendation.reversal_condition)
        self.assertEqual(len(recommendation.alternatives), 3)

    def test_phase_12_recommendation_contract_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            PrescriptiveAssessor().recommend(
                "",
                (Alternative("one", 1, 0),),
                constraints=(),
                downside_guardrails=(),
                reversal_condition="",
            )
        with self.assertRaises(ValueError):
            PrescriptiveAssessor().recommend(
                "objective",
                (
                    Alternative("one", 1, 0, feasible=False),
                    Alternative("two", 2, 0, guardrails_pass=False),
                ),
                constraints=("limit",),
                downside_guardrails=("safe",),
                reversal_condition="if evidence changes",
            )


if __name__ == "__main__":
    unittest.main()
