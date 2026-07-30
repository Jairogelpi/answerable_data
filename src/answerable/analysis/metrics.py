from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class MetricType(StrEnum):
    ADDITIVE = "additive"
    RATIO = "ratio"
    SEMI_ADDITIVE = "semi_additive"
    NON_ADDITIVE = "non_additive"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    metric_type: MetricType
    grain: tuple[str, ...]
    expression: str
    numerator: str | None = None
    denominator: str | None = None

    def __post_init__(self) -> None:
        if not self.metric_id or not self.grain or not self.expression:
            raise ValueError("metric id, grain, and expression are required")
        if self.metric_type is MetricType.RATIO and (
            self.numerator is None or self.denominator is None
        ):
            raise ValueError("ratio metrics require numerator and denominator")


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    metric_id: str
    before: float
    after: float
    absolute_difference: float
    relative_difference: float
    reconciled: bool
    blocked: bool


class MetricReconciler:
    def __init__(self, *, relative_tolerance: float = 1e-6) -> None:
        if relative_tolerance < 0:
            raise ValueError("relative_tolerance cannot be negative")
        self._relative_tolerance = relative_tolerance

    def reconcile(
        self, metric: MetricDefinition, *, before: float, after: float
    ) -> ReconciliationResult:
        absolute = abs(after - before)
        relative = absolute / abs(before) if before else (0.0 if after == 0 else math.inf)
        reconciled = relative <= self._relative_tolerance
        return ReconciliationResult(
            metric_id=metric.metric_id,
            before=before,
            after=after,
            absolute_difference=absolute,
            relative_difference=relative,
            reconciled=reconciled,
            blocked=not reconciled,
        )
