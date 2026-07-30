from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from answerable.ingestion.models import DataProfile


class GrainStatus(StrEnum):
    UNIQUE = "unique"
    AMBIGUOUS = "ambiguous"
    NO_KEY = "no_key"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class GrainResult:
    status: GrainStatus
    candidate_keys: tuple[tuple[str, ...], ...]
    row_count: int


class GrainAnalyzer:
    def infer(self, profile: DataProfile) -> GrainResult:
        if profile.row_count == 0:
            return GrainResult(GrainStatus.EMPTY, (), 0)
        candidates = tuple(
            (column.name,)
            for column in profile.columns
            if column.null_count == 0 and column.distinct_count == profile.row_count
        )
        if len(candidates) == 1:
            status = GrainStatus.UNIQUE
        elif len(candidates) > 1:
            status = GrainStatus.AMBIGUOUS
        else:
            status = GrainStatus.NO_KEY
        return GrainResult(status, candidates, profile.row_count)
