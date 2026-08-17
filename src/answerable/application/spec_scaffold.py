"""Scaffold a question.yaml from a data file's own columns.

Hand-writing question.yaml from the schema reference is the single biggest
piece of friction between "I have a CSV" and a first `answerable assess`.
This module inspects the file's columns (via the same FileInspector used by
the real assessment) and guesses plausible roles for them -- entity,
event time, treatment, outcome, covariates -- then writes a question.yaml
with those guesses filled in and every field a human must actually decide
(the question text, the claims, the causal strategy) marked with a comment.

The guesses are a starting point, not a verdict: `answerable assess` still
runs the real checks against whatever the user confirms or edits.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from answerable.ingestion.files import FileInspector
from answerable.ingestion.models import ColumnProfile, DataAssetSnapshot

_NUMERIC_TYPES = (
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "BIGINT",
    "HUGEINT",
    "FLOAT",
    "DOUBLE",
    "DECIMAL",
    "BOOLEAN",  # a true/false outcome column casts cleanly to 1.0/0.0
)
_TIME_TYPES = ("DATE", "TIMESTAMP", "TIME")


def _looks_numeric(column: ColumnProfile) -> bool:
    return any(column.physical_type.upper().startswith(kind) for kind in _NUMERIC_TYPES)


def _looks_temporal(column: ColumnProfile) -> bool:
    upper = column.physical_type.upper()
    if any(upper.startswith(kind) for kind in _TIME_TYPES):
        return True
    return any(hint in column.name.lower() for hint in ("date", "time", "_at", "timestamp"))


@dataclass(frozen=True, slots=True)
class RoleGuesses:
    entity_column: str | None
    event_time_column: str | None
    treatment_column: str | None
    outcome_column: str | None
    covariate_columns: tuple[str, ...]

    @property
    def unresolved(self) -> tuple[str, ...]:
        required = ("entity_column", "event_time_column", "treatment_column", "outcome_column")
        return tuple(name for name in required if getattr(self, name) is None)


def guess_roles(snapshot: DataAssetSnapshot) -> RoleGuesses:
    """Best-effort column-role guesses. Never raises: an unresolved role is None."""
    row_count = snapshot.profile.row_count
    remaining = {column.name: column for column in snapshot.profile.columns}

    def take(predicate: Callable[[ColumnProfile], bool]) -> str | None:
        for name, column in list(remaining.items()):
            if predicate(column):
                del remaining[name]
                return name
        return None

    treatment_hints = ("treatment", "exposed", "variant", "group", "test", "campaign", "arm")
    outcome_hints = ("outcome", "retained", "converted", "success", "label", "target", "churn")

    entity = take(lambda c: c.distinct_count == row_count and "id" in c.name.lower()) or take(
        lambda c: c.distinct_count == row_count
    )
    event_time = take(_looks_temporal)
    treatment = take(
        lambda c: c.distinct_count == 2 and any(h in c.name.lower() for h in treatment_hints)
    ) or take(lambda c: c.distinct_count == 2)
    outcome = (
        take(
            lambda c: (
                _looks_numeric(c)
                and c.distinct_count <= 2
                and any(h in c.name.lower() for h in outcome_hints)
            )
        )
        or take(lambda c: _looks_numeric(c) and c.distinct_count <= 2)
        or take(_looks_numeric)
    )
    covariates = tuple(
        name
        for name, column in remaining.items()
        if 1 < column.distinct_count <= max(2, row_count // 5)
    )
    return RoleGuesses(entity, event_time, treatment, outcome, covariates)


def scaffold_question(data_path: Path) -> str:
    """Inspect `data_path` and render a question.yaml scaffold as text."""
    inspector = FileInspector()
    try:
        snapshot = inspector.inspect(data_path)
    finally:
        inspector.close()
    roles = guess_roles(snapshot)
    columns = ", ".join(sorted(c.name for c in snapshot.profile.columns))
    warning = (
        f"# Could not guess: {', '.join(roles.unresolved)}. Fill these in by hand.\n"
        if roles.unresolved
        else ""
    )
    covariate_yaml = "[" + ", ".join(f'"{name}"' for name in roles.covariate_columns) + "]"
    entity = roles.entity_column or "TODO"
    event_time = roles.event_time_column or "TODO"
    treatment = roles.treatment_column or "TODO"
    outcome = roles.outcome_column or "TODO"
    return f"""# Scaffolded from {data_path.name} ({snapshot.row_count} rows). Columns seen:
# {columns}
{warning}# Every guessed *_column below came from this file's own schema (unique ID
# column, low-cardinality column, numeric column, date/time-typed column).
# Everything else on this page is a decision only you can make -- the
# question being asked, which claims should be checked, and the causal
# design -- so it's left as an explicit choice below, not guessed.
question_id: q_{data_path.stem}
raw_question: "TODO: state the question in one sentence, e.g. 'Did X increase Y?'"
normalized_question: "TODO: same question, normalized"
language: en
analysis_type: causal  # or: descriptive, predictive
unit_of_analysis: "TODO: e.g. customer, order, session"
population:
  description: "TODO: who/what is in scope"
  inclusion: []
outcome:
  metric_id: "TODO: short id, e.g. retention_90d"
  definition: "TODO: one sentence definition"
  value_type: ratio
time:
  observation_start: "2025-01-01T00:00:00+00:00"  # TODO
  observation_end: "2025-06-30T00:00:00+00:00"  # TODO
data:
  entity_column: {entity}
  event_time_column: {event_time}
  treatment_column: {treatment}
  outcome_column: {outcome}
  covariate_columns: {covariate_yaml}
  observation_window_days: 90  # TODO
  analysis_end: "2025-06-30T00:00:00+00:00"  # TODO, usually == time.observation_end
causal:
  treatment: {treatment}
  outcome: {outcome}
  population: "TODO"
  estimand: "TODO: e.g. Average treatment effect of X on Y"
  strategy: regression_adjustment  # or: randomized, difference_in_differences, ...
  adjustment_set: {covariate_yaml}
  assumptions:
    - "TODO: what you're assuming to identify this effect"
claims:
  - text: "TODO: the descriptive claim, e.g. 'Treated customers had higher observed Y.'"
    claim_class: descriptive
  - text: "TODO: the causal claim you actually want to make"
    claim_class: causal
"""


__all__ = ["RoleGuesses", "guess_roles", "scaffold_question"]
