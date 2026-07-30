from __future__ import annotations

import unittest

from answerable.domain.models import Verdict
from answerable.evidence.claims import ClaimClass, ClaimContext, ClaimLinter
from answerable.evidence.verdict import (
    FindingInput,
    Repairability,
    RepairItem,
    RepairPlanGenerator,
    VerdictEngine,
)

FR_VERDICT_001 = "FR-VERDICT-001"
FR_VERDICT_002 = "FR-VERDICT-002"
FR_VERDICT_003 = "FR-VERDICT-003"
FR_VERDICT_004 = "FR-VERDICT-004"
FR_VERDICT_005 = "FR-VERDICT-005"
FR_VERDICT_006 = "FR-VERDICT-006"


class VerdictAndClaimTests(unittest.TestCase):
    def finding(
        self, category: str, severity: str = "blocker", all_claims: bool = False
    ) -> FindingInput:
        return FindingInput(
            "f", category, severity, category, all_claims, Repairability.RECOVERABLE
        )

    def test_phase_13_applies_deterministic_precedence(self) -> None:
        cases = (
            ("execution_fatal", Verdict.ASSESSMENT_INCOMPLETE),
            ("misleading_question", Verdict.MISLEADING_QUESTION),
            ("identification", Verdict.FUNDAMENTALLY_UNIDENTIFIABLE),
            ("missing_evidence", Verdict.NOT_ANSWERABLE_YET),
            ("power", Verdict.INSUFFICIENT_POWER),
            ("partial", Verdict.PARTIALLY_ANSWERABLE),
        )
        for category, verdict in cases:
            with self.subTest(category=category):
                self.assertEqual(VerdictEngine().decide((self.finding(category),)).verdict, verdict)
        integrity = self.finding("data_integrity", all_claims=True)
        self.assertEqual(
            VerdictEngine().decide((integrity,)).verdict, Verdict.DATA_INTEGRITY_FAILURE
        )
        assumption = self.finding("assumption", "warning")
        self.assertEqual(
            VerdictEngine().decide((assumption,)).verdict, Verdict.ANSWERABLE_WITH_ASSUMPTIONS
        )
        self.assertEqual(VerdictEngine().decide(()).verdict, Verdict.ANSWERABLE)

    def test_phase_13_claim_linter_separates_allowed_and_forbidden(self) -> None:
        good = ClaimContext(ClaimClass.DESCRIPTIVE, "customers", "2026")
        bad = ClaimContext(ClaimClass.ASSOCIATION, None, None, causal_gate=False)
        result = VerdictEngine().decide(
            (), claims=(("Revenue rose", good), ("Campaign caused revenue", bad))
        )
        self.assertEqual(result.allowed_claims, ("Revenue rose",))
        self.assertEqual(result.forbidden_claims, ("Campaign caused revenue",))
        violations = ClaimLinter().lint(
            "No effect; subgroup relative % increase",
            ClaimContext(ClaimClass.RECOMMENDATION, "users", "2026", subgroup_reliable=False),
        )
        self.assertEqual(
            set(violations),
            {
                "absence_claim_from_nonsignificance",
                "relative_change_without_baseline",
                "unreliable_subgroup_claim",
                "recommendation_without_decision",
            },
        )

    def test_phase_13_blockers_require_repairability_and_plan_is_minimal(self) -> None:
        with self.assertRaises(ValueError):
            VerdictEngine().decide((FindingInput("x", "power", "blocker", "x"),))

        def item(name: str, cost: int) -> RepairItem:
            return RepairItem(
                name,
                "validity",
                True,
                "collect",
                "user",
                "customers",
                "30d",
                100,
                "answerable",
                cost,
                1,
                "descriptive question",
            )

        plan = RepairPlanGenerator().minimal((item("expensive", 10), item("cheap", 1)))
        self.assertEqual(plan[0].missing_information, "cheap")


if __name__ == "__main__":
    unittest.main()
