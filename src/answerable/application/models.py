from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from answerable.causal.contract import CausalContract
from answerable.domain.models import QuestionContract, Verdict
from answerable.evidence.claims import ClaimClass
from answerable.evidence.verdict import FindingInput
from answerable.warrants.service import WarrantRecord


@dataclass(frozen=True, slots=True)
class DataMapping:
    """Column roles the checks need. Declared, never guessed."""

    entity_column: str
    event_time_column: str
    treatment_column: str
    outcome_column: str
    observation_window_days: int
    analysis_end: datetime
    covariate_columns: tuple[str, ...] = ()
    prediction_time_column: str | None = None
    feature_available_time_column: str | None = None
    metric_definition_column: str | None = None

    def __post_init__(self) -> None:
        if self.observation_window_days <= 0:
            raise ValueError("observation_window_days must be positive")
        if self.analysis_end.tzinfo is None:
            raise ValueError("analysis_end must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ClaimCandidate:
    text: str
    claim_class: ClaimClass


@dataclass(frozen=True, slots=True)
class AssessmentSpec:
    contract: QuestionContract
    mapping: DataMapping
    causal: CausalContract
    claims: tuple[ClaimCandidate, ...]


@dataclass(frozen=True, slots=True)
class AssessmentRun:
    assessment_id: str
    verdict: Verdict
    blockers: tuple[FindingInput, ...]
    allowed_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    observations: dict[str, object]
    warrant: WarrantRecord
    artifacts: dict[str, Path]
