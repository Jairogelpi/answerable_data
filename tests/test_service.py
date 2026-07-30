from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from answerable.application.service import AssessmentService
from answerable.domain.lifecycle import AssessmentState
from answerable.persistence.sqlite import SQLiteAssessmentRepository


class AssessmentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = SQLiteAssessmentRepository(Path(self.tempdir.name) / "answerable.db")
        self.service = AssessmentService(self.repository)

    def tearDown(self) -> None:
        self.repository.close()
        self.tempdir.cleanup()

    def test_FR_LIFE_003_repeated_create_is_idempotent(self) -> None:
        first = self.service.create_assessment("ws_01", "actor_01", "idem-01")
        second = self.service.create_assessment("ws_01", "actor_01", "idem-01")
        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.list_audit_events(first.assessment_id)), 1)

    def test_FR_LIFE_007_transition_creates_attributable_audit_event(self) -> None:
        created = self.service.create_assessment("ws_01", "actor_01", "idem-01")
        moved = self.service.transition(
            created.assessment_id,
            AssessmentState.FRAMING,
            actor_id="actor_02",
            expected_version=1,
            idempotency_key="idem-02",
        )
        events = self.repository.list_audit_events(created.assessment_id)
        self.assertEqual(moved.state, AssessmentState.FRAMING)
        self.assertEqual([event.actor_id for event in events], ["actor_01", "actor_02"])
        self.assertEqual(events[-1].previous_version, 1)
        self.assertEqual(events[-1].new_version, 2)

    def test_FR_LIFE_003_repeated_transition_does_not_duplicate_audit(self) -> None:
        created = self.service.create_assessment("ws_01", "actor_01", "idem-01")
        first = self.service.transition(
            created.assessment_id,
            AssessmentState.FRAMING,
            actor_id="actor_02",
            expected_version=1,
            idempotency_key="idem-02",
        )
        second = self.service.transition(
            created.assessment_id,
            AssessmentState.FRAMING,
            actor_id="actor_02",
            expected_version=1,
            idempotency_key="idem-02",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.repository.list_audit_events(created.assessment_id)), 2)


if __name__ == "__main__":
    unittest.main()
