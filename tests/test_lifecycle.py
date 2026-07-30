from __future__ import annotations

import unittest

from answerable.domain.lifecycle import (
    AssessmentState,
    InvalidStateTransition,
    can_transition,
    transition,
)


class LifecycleTests(unittest.TestCase):
    def test_FR_LIFE_001_accepts_declared_transition(self) -> None:
        self.assertTrue(can_transition(AssessmentState.DRAFT, AssessmentState.FRAMING))
        self.assertEqual(
            transition(AssessmentState.DRAFT, AssessmentState.FRAMING),
            AssessmentState.FRAMING,
        )

    def test_FR_LIFE_002_rejects_invalid_transition_with_typed_error(self) -> None:
        with self.assertRaises(InvalidStateTransition) as caught:
            transition(AssessmentState.DRAFT, AssessmentState.ISSUED)
        self.assertEqual(caught.exception.current, AssessmentState.DRAFT)
        self.assertEqual(caught.exception.requested, AssessmentState.ISSUED)

    def test_FR_LIFE_005_failed_assessment_resumes_only_at_allowed_checkpoint(self) -> None:
        self.assertTrue(can_transition(AssessmentState.FAILED, AssessmentState.PROFILING))
        self.assertTrue(can_transition(AssessmentState.FAILED, AssessmentState.PLANNING))
        self.assertFalse(can_transition(AssessmentState.FAILED, AssessmentState.ISSUED))

    def test_FR_LIFE_001_terminal_states_do_not_transition(self) -> None:
        self.assertFalse(can_transition(AssessmentState.SUPERSEDED, AssessmentState.DRAFT))


if __name__ == "__main__":
    unittest.main()
