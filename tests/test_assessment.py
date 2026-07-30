from __future__ import annotations

import unittest

from answerable.domain.assessment import Assessment, ImmutableAssessmentError
from answerable.domain.lifecycle import AssessmentState


class AssessmentTests(unittest.TestCase):
    def test_FR_LIFE_004_issued_assessment_is_immutable(self) -> None:
        assessment = Assessment.create("asm_01", "workspace_01", "actor_01")
        object.__setattr__(assessment, "state", AssessmentState.ISSUED)
        with self.assertRaises(ImmutableAssessmentError):
            assessment.with_question_contract("qst_01")

    def test_FR_LIFE_006_cancellation_preserves_completed_artifacts(self) -> None:
        assessment = Assessment.create("asm_01", "workspace_01", "actor_01")
        object.__setattr__(assessment, "state", AssessmentState.EXECUTING)
        object.__setattr__(assessment, "artifact_ids", ("art_01",))
        cancelled = assessment.cancel()
        self.assertEqual(cancelled.state, AssessmentState.FAILED)
        self.assertEqual(cancelled.artifact_ids, ("art_01",))
        self.assertTrue(cancelled.cancelled)

    def test_FR_LIFE_004_new_versions_are_immutable_values(self) -> None:
        original = Assessment.create("asm_01", "workspace_01", "actor_01")
        changed = original.move_to(AssessmentState.FRAMING)
        self.assertEqual(original.state, AssessmentState.DRAFT)
        self.assertEqual(changed.state, AssessmentState.FRAMING)
        self.assertEqual(changed.version, original.version + 1)

    def test_FR_LIFE_004_question_contract_requires_mutable_assessment_and_id(self) -> None:
        original = Assessment.create("asm_01", "workspace_01", "actor_01")
        with self.assertRaisesRegex(ValueError, "required"):
            original.with_question_contract(" ")
        changed = original.with_question_contract("qst_01")
        self.assertEqual(changed.question_contract_id, "qst_01")
        self.assertEqual(changed.version, 2)

    def test_FR_LIFE_006_cancellation_rejects_draft(self) -> None:
        original = Assessment.create("asm_01", "workspace_01", "actor_01")
        with self.assertRaisesRegex(ValueError, "cannot be cancelled"):
            original.cancel()

    def test_FR_LIFE_004_superseded_assessment_is_immutable(self) -> None:
        assessment = Assessment.create("asm_01", "workspace_01", "actor_01")
        object.__setattr__(assessment, "state", AssessmentState.SUPERSEDED)
        with self.assertRaises(ImmutableAssessmentError):
            assessment.move_to(AssessmentState.DRAFT)


if __name__ == "__main__":
    unittest.main()
