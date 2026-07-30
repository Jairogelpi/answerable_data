from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import sqlglot
from sqlglot import exp

from answerable.execution.duckdb_readonly import DuckDBReadOnlyExecutor


@dataclass(frozen=True, slots=True)
class ConnectorCapabilities:
    catalog: bool
    read_only_query: bool
    pushdown: bool
    cancellation: bool


class EnterpriseConnector(Protocol):
    @property
    def capabilities(self) -> ConnectorCapabilities: ...
    def test(self) -> bool: ...
    def catalog(self) -> tuple[str, ...]: ...
    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]: ...


class ConnectorConformance:
    def validate(self, connector: EnterpriseConnector) -> None:
        if not connector.test():
            raise ValueError("connector health check failed")
        if not connector.capabilities.catalog or not connector.capabilities.read_only_query:
            raise ValueError("connector lacks required read-only capabilities")
        if not connector.catalog():
            raise ValueError("connector catalog is empty")
        try:
            connector.query("DELETE FROM protected", max_rows=1)
        except (PermissionError, ValueError):
            return
        raise ValueError("connector accepted a mutation")


def _read_only_sql(sql: str) -> str:
    try:
        statements = sqlglot.parse(sql)
    except sqlglot.errors.ParseError as error:
        raise ValueError("query could not be parsed") from error
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise PermissionError("only one read-only query is allowed")
    return statements[0].sql()


class SQLiteConnector:
    capabilities = ConnectorCapabilities(True, True, False, False)

    def __init__(self, path: Path) -> None:
        resolved = path.resolve()
        if not resolved.is_file():
            raise ValueError("SQLite database does not exist")
        self._connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)

    def close(self) -> None:
        self._connection.close()

    def test(self) -> bool:
        return bool(self._connection.execute("SELECT 1").fetchone() == (1,))

    def catalog(self) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        normalized = _read_only_sql(sql)
        cursor = self._connection.execute(
            f"SELECT * FROM ({normalized}) AS answerable_result LIMIT ?", (max_rows + 1,)
        )
        columns = tuple(item[0] for item in cursor.description)
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise ValueError("query result exceeds row limit")
        return tuple(dict(zip(columns, row, strict=True)) for row in rows)


class DuckDBConnector:
    capabilities = ConnectorCapabilities(True, True, True, False)

    def __init__(self, executor: DuckDBReadOnlyExecutor) -> None:
        self._executor = executor

    def test(self) -> bool:
        return self._executor.connection.execute("SELECT 1").fetchone() == (1,)

    def catalog(self) -> tuple[str, ...]:
        rows = self._executor.connection.execute("SHOW TABLES").fetchall()
        return tuple(str(row[0]) for row in rows)

    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]:
        result = self._executor.execute(sql, max_rows=max_rows)
        if result.truncated:
            raise ValueError("query result exceeds row limit")
        return tuple(dict(zip(result.columns, row, strict=True)) for row in result.rows)


class DBAPIReadOnlyConnector:
    """Concrete adapter for PostgreSQL-compatible DB-API connections."""

    capabilities = ConnectorCapabilities(True, True, True, True)

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def test(self) -> bool:
        cursor = self._connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("SELECT 1")
        return tuple(cursor.fetchone()) == (1,)

    def catalog(self) -> tuple[str, ...]:
        cursor = self._connection.cursor()  # type: ignore[attr-defined]
        cursor.execute(
            "SELECT table_schema || '.' || table_name "
            "FROM information_schema.tables WHERE table_type = 'BASE TABLE' "
            "ORDER BY table_schema, table_name"
        )
        return tuple(str(row[0]) for row in cursor.fetchall())

    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]:
        if max_rows <= 0:
            raise ValueError("max_rows must be positive")
        normalized = _read_only_sql(sql)
        cursor = self._connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            f"SELECT * FROM ({normalized}) AS answerable_result LIMIT %s", (max_rows + 1,)
        )
        columns = tuple(item[0] for item in cursor.description)
        rows = cursor.fetchmany(max_rows + 1)
        if len(rows) > max_rows:
            raise ValueError("query result exceeds row limit")
        return tuple(dict(zip(columns, row, strict=True)) for row in rows)
