from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from answerable.domain.assessment import Assessment, AuditEvent
from answerable.domain.lifecycle import AssessmentState
from answerable.domain.serialization import fingerprint
from answerable.persistence.sqlite import SQLiteAssessmentRepository


class AssessmentService:
    def __init__(self, repository: SQLiteAssessmentRepository) -> None:
        self._repository = repository

    def create_assessment(
        self,
        workspace_id: str,
        actor_id: str,
        idempotency_key: str,
        *,
        now: datetime | None = None,
    ) -> Assessment:
        request_hash = fingerprint(
            {"operation": "create", "workspace_id": workspace_id, "actor_id": actor_id}
        )
        previous = self._repository.get_idempotency(idempotency_key, request_hash)
        if previous is not None:
            return self._repository.get(json.loads(previous)["assessment_id"])

        timestamp = now or datetime.now(UTC)
        assessment = Assessment.create(f"asm_{uuid4().hex}", workspace_id, actor_id, now=timestamp)
        self._repository.add(assessment)
        self._repository.append_audit_event(
            AuditEvent(
                event_id=f"evt_{uuid4().hex}",
                assessment_id=assessment.assessment_id,
                actor_id=actor_id,
                action="assessment.created",
                previous_version=None,
                new_version=assessment.version,
                occurred_at=timestamp,
            )
        )
        self._repository.claim_idempotency(
            idempotency_key,
            request_hash,
            json.dumps({"assessment_id": assessment.assessment_id}, separators=(",", ":")),
        )
        return assessment

    def transition(
        self,
        assessment_id: str,
        requested: AssessmentState,
        *,
        actor_id: str,
        expected_version: int,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> Assessment:
        request_hash = fingerprint(
            {
                "operation": "transition",
                "assessment_id": assessment_id,
                "requested": requested.value,
                "actor_id": actor_id,
                "expected_version": expected_version,
            }
        )
        previous = self._repository.get_idempotency(idempotency_key, request_hash)
        if previous is not None:
            response = json.loads(previous)
            return next(
                item
                for item in self._repository.history(assessment_id)
                if item.version == response["version"]
            )

        current = self._repository.get(assessment_id)
        changed = current.move_to(requested, now=now)
        self._repository.save(changed, expected_version=expected_version)
        timestamp = now or changed.updated_at
        self._repository.append_audit_event(
            AuditEvent(
                event_id=f"evt_{uuid4().hex}",
                assessment_id=assessment_id,
                actor_id=actor_id,
                action=f"assessment.transitioned.{requested.value}",
                previous_version=current.version,
                new_version=changed.version,
                occurred_at=timestamp,
            )
        )
        self._repository.claim_idempotency(
            idempotency_key,
            request_hash,
            json.dumps(
                {"assessment_id": assessment_id, "version": changed.version},
                separators=(",", ":"),
            ),
        )
        return changed
