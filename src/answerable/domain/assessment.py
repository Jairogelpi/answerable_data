from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from answerable.domain.lifecycle import AssessmentState, transition


class ImmutableAssessmentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Assessment:
    assessment_id: str
    workspace_id: str
    created_by: str
    state: AssessmentState
    version: int
    created_at: datetime
    updated_at: datetime
    question_contract_id: str | None = None
    artifact_ids: tuple[str, ...] = ()
    cancelled: bool = False

    @classmethod
    def create(
        cls,
        assessment_id: str,
        workspace_id: str,
        actor_id: str,
        *,
        now: datetime | None = None,
    ) -> Assessment:
        timestamp = now or datetime.now(UTC)
        return cls(
            assessment_id=assessment_id,
            workspace_id=workspace_id,
            created_by=actor_id,
            state=AssessmentState.DRAFT,
            version=1,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _ensure_mutable(self) -> None:
        if self.state in {AssessmentState.ISSUED, AssessmentState.SUPERSEDED}:
            raise ImmutableAssessmentError(f"{self.state.value} assessments are immutable")

    def move_to(self, state: AssessmentState, *, now: datetime | None = None) -> Assessment:
        self._ensure_mutable()
        next_state = transition(self.state, state)
        return replace(
            self,
            state=next_state,
            version=self.version + 1,
            updated_at=now or datetime.now(UTC),
        )

    def with_question_contract(
        self, question_contract_id: str, *, now: datetime | None = None
    ) -> Assessment:
        self._ensure_mutable()
        if not question_contract_id.strip():
            raise ValueError("question_contract_id is required")
        return replace(
            self,
            question_contract_id=question_contract_id,
            version=self.version + 1,
            updated_at=now or datetime.now(UTC),
        )

    def cancel(self, *, now: datetime | None = None) -> Assessment:
        self._ensure_mutable()
        if self.state not in {
            AssessmentState.FRAMING,
            AssessmentState.AWAITING_CLARIFICATION,
            AssessmentState.PROFILING,
            AssessmentState.PLANNING,
            AssessmentState.AWAITING_APPROVAL,
            AssessmentState.EXECUTING,
            AssessmentState.SYNTHESIZING,
        }:
            raise ValueError(f"assessment cannot be cancelled from {self.state.value}")
        return replace(
            self,
            state=AssessmentState.FAILED,
            cancelled=True,
            version=self.version + 1,
            updated_at=now or datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    assessment_id: str
    actor_id: str
    action: str
    previous_version: int | None
    new_version: int
    occurred_at: datetime
