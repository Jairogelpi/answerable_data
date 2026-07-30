from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class AnalysisType(StrEnum):
    DESCRIPTIVE = "descriptive"
    COMPARATIVE = "comparative"
    DIAGNOSTIC = "diagnostic"
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    PRESCRIPTIVE = "prescriptive"


class Verdict(StrEnum):
    ANSWERABLE = "ANSWERABLE"
    ANSWERABLE_WITH_ASSUMPTIONS = "ANSWERABLE_WITH_ASSUMPTIONS"
    PARTIALLY_ANSWERABLE = "PARTIALLY_ANSWERABLE"
    NOT_ANSWERABLE_YET = "NOT_ANSWERABLE_YET"
    FUNDAMENTALLY_UNIDENTIFIABLE = "FUNDAMENTALLY_UNIDENTIFIABLE"
    MISLEADING_QUESTION = "MISLEADING_QUESTION"
    INSUFFICIENT_POWER = "INSUFFICIENT_POWER"
    DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
    ASSESSMENT_INCOMPLETE = "ASSESSMENT_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class Population:
    description: str
    inclusion: tuple[str, ...] = ()
    exclusion: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("population description is required")


@dataclass(frozen=True, slots=True)
class Metric:
    metric_id: str
    definition: str
    value_type: str
    numerator: str | None = None
    denominator: str | None = None

    def __post_init__(self) -> None:
        if not self.metric_id.strip() or not self.definition.strip():
            raise ValueError("metric id and definition are required")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("ratio metrics require both numerator and denominator")


@dataclass(frozen=True, slots=True)
class TimeWindow:
    observation_start: datetime
    observation_end: datetime

    def __post_init__(self) -> None:
        if self.observation_start.tzinfo is None or self.observation_end.tzinfo is None:
            raise ValueError("time-window datetimes must be timezone-aware")
        if self.observation_start >= self.observation_end:
            raise ValueError("observation_start must precede observation_end")


@dataclass(frozen=True, slots=True)
class QuestionContract:
    question_id: str
    raw_question: str
    normalized_question: str
    language: str
    analysis_type: AnalysisType
    population: Population
    unit_of_analysis: str
    outcome: Metric
    time: TimeWindow
    assumptions: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    schema_version: str = field(default="1.0", init=False)

    def __post_init__(self) -> None:
        required = (
            self.question_id,
            self.raw_question,
            self.normalized_question,
            self.language,
            self.unit_of_analysis,
        )
        if any(not value.strip() for value in required):
            raise ValueError("question contract required fields cannot be blank")


@dataclass(frozen=True, slots=True)
class CheckSpec:
    check_id: str
    check_type: str
    check_version: str
    requirement_id: str
    executor: str
    severity_on_failure: str
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CheckPlan:
    plan_id: str
    assessment_id: str
    checks: tuple[CheckSpec, ...]
    schema_version: str = field(default="1.0", init=False)


@dataclass(frozen=True, slots=True)
class ExecutionArtifact:
    artifact_id: str
    check_id: str
    status: str
    input_fingerprints: tuple[str, ...]
    output_hash: str
    result: dict[str, object]
    created_at: datetime
    schema_version: str = field(default="1.0", init=False)


@dataclass(frozen=True, slots=True)
class EvidenceNode:
    node_id: str
    node_type: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    source_id: str
    target_id: str
    edge_type: str


@dataclass(frozen=True, slots=True)
class EvidenceGraph:
    graph_id: str
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]
    schema_version: str = field(default="1.0", init=False)


@dataclass(frozen=True, slots=True)
class Warrant:
    warrant_id: str
    assessment_id: str
    version: int
    verdict: Verdict
    allowed_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    evidence_graph_id: str
    issued_at: datetime
    schema_version: str = field(default="1.0", init=False)
