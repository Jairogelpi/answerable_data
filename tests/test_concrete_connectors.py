from __future__ import annotations

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from answerable.enterprise import DBAPIReadOnlyConnector, DuckDBConnector, SQLiteConnector
from answerable.enterprise.connectors import ConnectorConformance
from answerable.execution.duckdb_readonly import DuckDBReadOnlyExecutor

FR_CONNECTOR_001 = "FR-CONNECTOR-001"
FR_CONNECTOR_002 = "FR-CONNECTOR-002"
FR_CONNECTOR_003 = "FR-CONNECTOR-003"


class ConcreteConnectorTests(unittest.TestCase):
    def test_sqlite_connector_reads_real_database_and_rejects_mutation(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "analytics.sqlite"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE metrics (name TEXT, value INTEGER)")
            connection.executemany(
                "INSERT INTO metrics VALUES (?, ?)", (("revenue", 10), ("orders", 2))
            )
            connection.commit()
            connection.close()

            with closing(SQLiteConnector(path)) as connector:
                self.assertTrue(connector.test())
                self.assertEqual(connector.catalog(), ("metrics",))
                self.assertEqual(
                    connector.query("SELECT * FROM metrics ORDER BY name", max_rows=2),
                    (
                        {"name": "orders", "value": 2},
                        {"name": "revenue", "value": 10},
                    ),
                )
                with self.assertRaises(PermissionError):
                    connector.query("DELETE FROM metrics", max_rows=1)

    def test_sqlite_connector_enforces_result_bound(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "analytics.sqlite"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE values_table (value INTEGER)")
            connection.executemany("INSERT INTO values_table VALUES (?)", ((1,), (2,)))
            connection.commit()
            connection.close()
            with closing(SQLiteConnector(path)) as connector:
                with self.assertRaisesRegex(ValueError, "row limit"):
                    connector.query("SELECT * FROM values_table", max_rows=1)
                with self.assertRaisesRegex(ValueError, "positive"):
                    connector.query("SELECT * FROM values_table", max_rows=0)

    def test_sqlite_connector_rejects_missing_database(self) -> None:
        with (
            TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "does not exist"),
        ):
            SQLiteConnector(Path(directory) / "missing.sqlite")

    def test_duckdb_connector_uses_guarded_executor(self) -> None:
        executor = DuckDBReadOnlyExecutor()
        self.addCleanup(executor.close)
        executor.register_rows("metrics", ({"value": 1}, {"value": 2}))
        connector = DuckDBConnector(executor)
        self.assertTrue(connector.test())
        self.assertEqual(connector.catalog(), ("metrics",))
        self.assertEqual(
            connector.query("SELECT sum(value) AS total FROM metrics", max_rows=1),
            ({"total": 3},),
        )

    def test_dbapi_connector_uses_read_only_transaction_and_bounds(self) -> None:
        class Cursor:
            description = (("answer",),)

            def __init__(self) -> None:
                self.executed: list[str] = []

            def execute(self, sql: str, parameters: object = None) -> None:
                del parameters
                self.executed.append(sql)

            def fetchone(self) -> tuple[int]:
                return (1,)

            def fetchall(self) -> list[tuple[str]]:
                return [("public.metrics",)]

            def fetchmany(self, size: int) -> list[tuple[int]]:
                return [(42,)][:size]

        class Connection:
            def __init__(self) -> None:
                self.cursors: list[Cursor] = []

            def cursor(self) -> Cursor:
                cursor = Cursor()
                self.cursors.append(cursor)
                return cursor

        connection = Connection()
        connector = DBAPIReadOnlyConnector(connection)
        self.assertTrue(connector.test())
        self.assertEqual(connector.catalog(), ("public.metrics",))
        self.assertEqual(connector.query("SELECT 42 AS answer", max_rows=1), ({"answer": 42},))
        self.assertTrue(
            any(
                "SET TRANSACTION READ ONLY" in sql
                for cursor in connection.cursors
                for sql in cursor.executed
            )
        )
        with self.assertRaises(PermissionError):
            connector.query("UPDATE metrics SET answer = 0", max_rows=1)
        with self.assertRaisesRegex(ValueError, "positive"):
            connector.query("SELECT 1", max_rows=0)

    def test_connector_conformance_rejects_invalid_contracts(self) -> None:
        class BrokenConnector:
            capabilities = SQLiteConnector.capabilities

            def test(self) -> bool:
                return False

            def catalog(self) -> tuple[str, ...]:
                return ()

            def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]:
                del sql, max_rows
                return ()

        with self.assertRaisesRegex(ValueError, "health check"):
            ConnectorConformance().validate(BrokenConnector())


if __name__ == "__main__":
    unittest.main()
