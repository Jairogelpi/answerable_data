from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AnalysisType(StrEnum):
    DESCRIPTIVE = "descriptive"
    DIAGNOSTIC = "diagnostic"
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Inference:
    value: str
    source: str
    confidence: float

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class FramingProposal:
    normalized_question: str
    analysis_type: AnalysisType
    fields: tuple[tuple[str, Inference], ...]
    ambiguities: tuple[str, ...]
    clarifications: tuple[str, ...]

    def field(self, name: str) -> Inference | None:
        return next((value for key, value in self.fields if key == name), None)
