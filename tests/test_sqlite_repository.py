from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from answerable.domain.assessment import Assessment
from answerable.domain.lifecycle import AssessmentState
from answerable.persistence.errors import (
    ConcurrencyConflict,
    ImmutableRecordError,
    RecordAlreadyExists,
    RecordNotFound,
)
from answerable.persistence.sqlite import SQLiteAssessmentRepository


class SQLiteRepositoryContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = SQLiteAssessmentRepository(Path(self.tempdir.name) / "answerable.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.tempdir.cleanup()

    def test_INV_011_versions_are_append_only(self) -> None:
        draft = Assessment.create("asm_01", "ws_01", "actor_01")
        self.repository.add(draft)
        framing = draft.move_to(AssessmentState.FRAMING)
        self.repository.save(framing, expected_version=1)
        self.assertEqual(self.repository.get("asm_01").version, 2)
        self.assertEqual([item.version for item in self.repository.history("asm_01")], [1, 2])

    def test_INV_011_issued_records_cannot_be_replaced(self) -> None:
        assessment = Assessment.create("asm_01", "ws_01", "actor_01")
        object.__setattr__(assessment, "state", AssessmentState.ISSUED)
        self.repository.add(assessment)
        changed = assessment
        object.__setattr__(changed, "version", 2)
        with self.assertRaises(ImmutableRecordError):
            self.repository.save(changed, expected_version=1)

    def test_FR_LIFE_003_idempotency_returns_original_result(self) -> None:
        first = self.repository.claim_idempotency("key-1", "request-a", '{"id":"asm_01"}')
        second = self.repository.claim_idempotency("key-1", "request-a", '{"ignored":true}')
        self.assertEqual(first, second)

    def test_FR_LIFE_003_idempotency_rejects_reused_key_for_different_request(self) -> None:
        self.repository.claim_idempotency("key-1", "request-a", "{}")
        with self.assertRaises(ConcurrencyConflict):
            self.repository.claim_idempotency("key-1", "request-b", "{}")
        with self.assertRaises(ConcurrencyConflict):
            self.repository.get_idempotency("key-1", "request-b")

    def test_INV_011_optimistic_concurrency_rejects_stale_version(self) -> None:
        draft = Assessment.create("asm_01", "ws_01", "actor_01")
        self.repository.add(draft)
        with self.assertRaises(ConcurrencyConflict):
            self.repository.save(draft.move_to(AssessmentState.FRAMING), expected_version=0)

    def test_INV_011_rejects_duplicate_identity(self) -> None:
        draft = Assessment.create("asm_01", "ws_01", "actor_01")
        self.repository.add(draft)
        with self.assertRaises(RecordAlreadyExists):
            self.repository.add(draft)

    def test_INV_011_missing_records_are_typed_errors(self) -> None:
        with self.assertRaises(RecordNotFound):
            self.repository.get("missing")
        with self.assertRaises(RecordNotFound):
            self.repository.history("missing")

    def test_INV_011_new_version_must_increment_once(self) -> None:
        draft = Assessment.create("asm_01", "ws_01", "actor_01")
        self.repository.add(draft)
        changed = draft.move_to(AssessmentState.FRAMING)
        object.__setattr__(changed, "version", 3)
        with self.assertRaisesRegex(ConcurrencyConflict, "increment"):
            self.repository.save(changed, expected_version=1)

    def test_INV_011_empty_audit_history_is_valid(self) -> None:
        self.assertEqual(self.repository.list_audit_events("missing"), [])


if __name__ == "__main__":
    unittest.main()
