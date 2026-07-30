from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class QualityContext:
    required_columns: frozenset[str] = frozenset()
    key_columns: tuple[str, ...] = ()
    unit_column: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: Severity
    message: str
    affected_columns: tuple[str, ...] = ()
    observed: float | int | str | None = None
    hypothesis_only: bool = False
