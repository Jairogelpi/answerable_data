from __future__ import annotations

from enum import StrEnum


class AssessmentState(StrEnum):
    DRAFT = "draft"
    FRAMING = "framing"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    PROFILING = "profiling"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    REVIEW = "review"
    ISSUED = "issued"
    REJECTED = "rejected"
    FAILED = "failed"
    SUPERSEDED = "superseded"


_TRANSITIONS: dict[AssessmentState, frozenset[AssessmentState]] = {
    AssessmentState.DRAFT: frozenset({AssessmentState.FRAMING}),
    AssessmentState.FRAMING: frozenset(
        {
            AssessmentState.AWAITING_CLARIFICATION,
            AssessmentState.PROFILING,
            AssessmentState.FAILED,
        }
    ),
    AssessmentState.AWAITING_CLARIFICATION: frozenset(
        {AssessmentState.FRAMING, AssessmentState.FAILED}
    ),
    AssessmentState.PROFILING: frozenset({AssessmentState.PLANNING, AssessmentState.FAILED}),
    AssessmentState.PLANNING: frozenset(
        {
            AssessmentState.AWAITING_APPROVAL,
            AssessmentState.EXECUTING,
            AssessmentState.FAILED,
        }
    ),
    AssessmentState.AWAITING_APPROVAL: frozenset(
        {AssessmentState.EXECUTING, AssessmentState.REJECTED, AssessmentState.FAILED}
    ),
    AssessmentState.EXECUTING: frozenset({AssessmentState.SYNTHESIZING, AssessmentState.FAILED}),
    AssessmentState.SYNTHESIZING: frozenset({AssessmentState.REVIEW, AssessmentState.FAILED}),
    AssessmentState.REVIEW: frozenset({AssessmentState.ISSUED, AssessmentState.REJECTED}),
    AssessmentState.ISSUED: frozenset({AssessmentState.SUPERSEDED}),
    AssessmentState.REJECTED: frozenset({AssessmentState.FRAMING}),
    AssessmentState.FAILED: frozenset(
        {
            AssessmentState.FRAMING,
            AssessmentState.PROFILING,
            AssessmentState.PLANNING,
            AssessmentState.EXECUTING,
        }
    ),
    AssessmentState.SUPERSEDED: frozenset(),
}


class InvalidStateTransition(ValueError):
    def __init__(self, current: AssessmentState, requested: AssessmentState) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"cannot transition assessment from {current.value} to {requested.value}")


def can_transition(current: AssessmentState, requested: AssessmentState) -> bool:
    return requested in _TRANSITIONS[current]


def transition(current: AssessmentState, requested: AssessmentState) -> AssessmentState:
    if not can_transition(current, requested):
        raise InvalidStateTransition(current, requested)
    return requested
