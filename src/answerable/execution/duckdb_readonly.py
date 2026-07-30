from __future__ import annotations

import re
from dataclasses import dataclass

import duckdb
import sqlglot
from sqlglot import exp

from answerable.execution.errors import UnsafeQuery

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return f'"{value}"'


@dataclass(frozen=True, slots=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


class DuckDBReadOnlyExecutor:
    def __init__(self) -> None:
        self._connection = duckdb.connect()
        self._registered: set[str] = set()

    def close(self) -> None:
        self._connection.close()

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._connection

    def register_rows(self, name: str, rows: tuple[dict[str, object], ...]) -> None:
        table = quote_identifier(name)
        if not rows:
            raise ValueError("at least one row is required")
        columns = tuple(rows[0])
        if not columns or any(tuple(row) != columns for row in rows):
            raise ValueError("all rows must contain the same ordered columns")
        definitions = ", ".join(
            f"{quote_identifier(column)} {self._duckdb_type(rows, column)}" for column in columns
        )
        self._connection.execute(f"CREATE TABLE {table} ({definitions})")
        placeholders = ", ".join("?" for _ in columns)
        self._connection.executemany(
            f"INSERT INTO {table} VALUES ({placeholders})",
            [tuple(row[column] for column in columns) for row in rows],
        )
        self._registered.add(name)

    def execute(self, sql: str, *, max_rows: int = 1000) -> QueryResult:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        normalized = self._validate(sql)
        cursor = self._connection.execute(
            f"SELECT * FROM ({normalized}) AS _answerable_result LIMIT {max_rows + 1}"
        )
        columns = tuple(item[0] for item in cursor.description)
        fetched = cursor.fetchall()
        return QueryResult(
            columns=columns,
            rows=tuple(tuple(value for value in row) for row in fetched[:max_rows]),
            truncated=len(fetched) > max_rows,
        )

    def _validate(self, sql: str) -> str:
        try:
            statements = sqlglot.parse(sql, read="duckdb")
        except sqlglot.errors.ParseError as error:
            raise UnsafeQuery("query could not be parsed") from error
        if len(statements) != 1 or not isinstance(statements[0], exp.Query):
            raise UnsafeQuery("exactly one read-only query is required")
        statement = statements[0]
        for function in statement.find_all(exp.Anonymous):
            raise UnsafeQuery(f"unregistered function is not allowed: {function.name}")
        common_tables = {cte.alias_or_name for cte in statement.find_all(exp.CTE)}
        allowed_tables = self._registered | common_tables
        for table in statement.find_all(exp.Table):
            if table.name not in allowed_tables:
                raise UnsafeQuery(f"unregistered relation is not allowed: {table.name}")
        return statement.sql(dialect="duckdb")

    @staticmethod
    def _duckdb_type(rows: tuple[dict[str, object], ...], column: str) -> str:
        value = next((row[column] for row in rows if row[column] is not None), None)
        if isinstance(value, bool):
            return "BOOLEAN"
        if isinstance(value, int):
            return "BIGINT"
        if isinstance(value, float):
            return "DOUBLE"
        return "VARCHAR"
