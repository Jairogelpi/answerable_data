from __future__ import annotations

import unittest

from answerable.execution.duckdb_readonly import DuckDBReadOnlyExecutor
from answerable.execution.errors import UnsafeQuery


class DuckDBReadOnlyExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.executor = DuckDBReadOnlyExecutor()
        self.executor.register_rows(
            "customers",
            (
                {"customer_id": 1, "revenue": 10.0},
                {"customer_id": 2, "revenue": 20.0},
            ),
        )

    def tearDown(self) -> None:
        self.executor.close()

    def test_FR_DATA_002_select_and_cte_are_allowed(self) -> None:
        result = self.executor.execute(
            "WITH totals AS (SELECT sum(revenue) AS total FROM customers) SELECT total FROM totals"
        )
        self.assertEqual(result.columns, ("total",))
        self.assertEqual(result.rows, ((30.0,),))

    def test_FR_DATA_002_mutations_and_multiple_statements_are_rejected(self) -> None:
        unsafe = (
            "CREATE TABLE stolen AS SELECT * FROM customers",
            "DELETE FROM customers",
            "SELECT * FROM customers; DROP TABLE customers",
            "COPY customers TO '/tmp/customers.csv'",
        )
        for query in unsafe:
            with self.subTest(query=query), self.assertRaises(UnsafeQuery):
                self.executor.execute(query)

    def test_FR_DATA_002_external_file_functions_are_rejected(self) -> None:
        with self.assertRaises(UnsafeQuery):
            self.executor.execute("SELECT * FROM read_csv_auto('/tmp/private.csv')")
        with self.assertRaises(UnsafeQuery):
            self.executor.execute("SELECT * FROM '/tmp/private.parquet'")
        with self.assertRaises(UnsafeQuery):
            self.executor.execute("SELECT * FROM unregistered_table")

    def test_phase_4_results_are_bounded(self) -> None:
        result = self.executor.execute("SELECT * FROM customers ORDER BY customer_id", max_rows=1)
        self.assertEqual(len(result.rows), 1)
        self.assertTrue(result.truncated)

    def test_phase_4_rejects_invalid_limits_and_sql(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            self.executor.execute("SELECT 1", max_rows=0)
        with self.assertRaises(UnsafeQuery):
            self.executor.execute("SELECT FROM")

    def test_phase_4_registration_rejects_unsafe_or_inconsistent_tables(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe identifier"):
            self.executor.register_rows("bad-name", ({"id": 1},))
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.executor.register_rows("empty", ())
        with self.assertRaisesRegex(ValueError, "same ordered"):
            self.executor.register_rows("mixed", ({"id": 1}, {"other": 2}))

    def test_phase_4_registration_supports_boolean_and_text_values(self) -> None:
        self.executor.register_rows(
            "features",
            (
                {"active": True, "label": "a"},
                {"active": False, "label": "b"},
            ),
        )
        result = self.executor.execute("SELECT * FROM features ORDER BY label")
        self.assertEqual(result.rows, ((True, "a"), (False, "b")))


if __name__ == "__main__":
    unittest.main()
