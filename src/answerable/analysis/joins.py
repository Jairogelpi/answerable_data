from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from answerable.execution.duckdb_readonly import DuckDBReadOnlyExecutor, quote_identifier


class JoinCardinality(StrEnum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


@dataclass(frozen=True, slots=True)
class JoinAssessment:
    cardinality: JoinCardinality
    left_rows: int
    right_rows: int
    output_rows: int
    fanout_ratio: float
    blocked: bool


class JoinAnalyzer:
    def __init__(self, executor: DuckDBReadOnlyExecutor) -> None:
        self._executor = executor

    def analyze(
        self,
        left: str,
        right: str,
        pairs: tuple[tuple[str, str], ...],
    ) -> JoinAssessment:
        if not pairs:
            raise ValueError("at least one join-key pair is required")
        left_table = quote_identifier(left)
        right_table = quote_identifier(right)
        left_keys = tuple(quote_identifier(pair[0]) for pair in pairs)
        right_keys = tuple(quote_identifier(pair[1]) for pair in pairs)
        left_rows = self._scalar(f"SELECT count(*) FROM {left_table}")
        right_rows = self._scalar(f"SELECT count(*) FROM {right_table}")
        left_many = self._has_duplicates(left_table, left_keys)
        right_many = self._has_duplicates(right_table, right_keys)
        if left_many and right_many:
            cardinality = JoinCardinality.MANY_TO_MANY
        elif left_many:
            cardinality = JoinCardinality.MANY_TO_ONE
        elif right_many:
            cardinality = JoinCardinality.ONE_TO_MANY
        else:
            cardinality = JoinCardinality.ONE_TO_ONE
        predicate = " AND ".join(
            f"l.{left_key} = r.{right_key}"
            for left_key, right_key in zip(left_keys, right_keys, strict=True)
        )
        output_rows = self._scalar(
            f"SELECT count(*) FROM {left_table} AS l JOIN {right_table} AS r ON {predicate}"
        )
        baseline = max(left_rows, 1)
        return JoinAssessment(
            cardinality=cardinality,
            left_rows=left_rows,
            right_rows=right_rows,
            output_rows=output_rows,
            fanout_ratio=output_rows / baseline,
            blocked=cardinality is JoinCardinality.MANY_TO_MANY,
        )

    def _has_duplicates(self, table: str, keys: tuple[str, ...]) -> bool:
        group = ", ".join(keys)
        value = self._scalar(
            f"SELECT count(*) FROM (SELECT {group} FROM {table} "
            f"GROUP BY {group} HAVING count(*) > 1) AS duplicates"
        )
        return value > 0

    def _scalar(self, sql: str) -> int:
        row = self._executor.connection.execute(sql).fetchone()
        if row is None:
            raise RuntimeError("scalar join query returned no result")
        return int(row[0])
