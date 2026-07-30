from __future__ import annotations

import unittest

from answerable.analysis.grain import GrainAnalyzer, GrainStatus
from answerable.analysis.joins import JoinAnalyzer, JoinCardinality
from answerable.execution.duckdb_readonly import DuckDBReadOnlyExecutor
from answerable.ingestion.models import ColumnProfile, DataProfile


class GrainAndJoinTests(unittest.TestCase):
    def test_FR_GRAIN_001_infers_candidate_keys_from_profile(self) -> None:
        profile = DataProfile(
            row_count=3,
            sampled=False,
            columns=(
                ColumnProfile("customer_id", "BIGINT", 0, 3),
                ColumnProfile("country", "VARCHAR", 0, 2),
            ),
        )
        result = GrainAnalyzer().infer(profile)
        self.assertEqual(result.status, GrainStatus.UNIQUE)
        self.assertEqual(result.candidate_keys, (("customer_id",),))

    def test_FR_GRAIN_007_reports_ambiguous_and_missing_keys(self) -> None:
        ambiguous = DataProfile(
            row_count=2,
            sampled=False,
            columns=(
                ColumnProfile("id", "BIGINT", 0, 2),
                ColumnProfile("email", "VARCHAR", 0, 2),
            ),
        )
        no_key = DataProfile(
            row_count=2,
            sampled=False,
            columns=(ColumnProfile("country", "VARCHAR", 0, 1),),
        )
        self.assertEqual(GrainAnalyzer().infer(ambiguous).status, GrainStatus.AMBIGUOUS)
        self.assertEqual(GrainAnalyzer().infer(no_key).status, GrainStatus.NO_KEY)
        self.assertEqual(
            GrainAnalyzer().infer(DataProfile(0, False, ())).status,
            GrainStatus.EMPTY,
        )

    def test_FR_GRAIN_004_many_to_many_join_is_blocked(self) -> None:
        executor = DuckDBReadOnlyExecutor()
        self.addCleanup(executor.close)
        executor.register_rows("orders", ({"k": 1}, {"k": 1}))
        executor.register_rows("campaigns", ({"k": 1}, {"k": 1}, {"k": 2}))
        result = JoinAnalyzer(executor).analyze("orders", "campaigns", (("k", "k"),))
        self.assertEqual(result.cardinality, JoinCardinality.MANY_TO_MANY)
        self.assertTrue(result.blocked)
        self.assertGreater(result.output_rows, result.left_rows)

    def test_FR_GRAIN_003_classifies_one_to_many_without_blocking(self) -> None:
        executor = DuckDBReadOnlyExecutor()
        self.addCleanup(executor.close)
        executor.register_rows("customers", ({"id": 1}, {"id": 2}))
        executor.register_rows(
            "orders",
            ({"customer_id": 1}, {"customer_id": 1}, {"customer_id": 2}),
        )
        result = JoinAnalyzer(executor).analyze("customers", "orders", (("id", "customer_id"),))
        self.assertEqual(result.cardinality, JoinCardinality.ONE_TO_MANY)
        self.assertFalse(result.blocked)

    def test_FR_GRAIN_003_classifies_many_to_one_and_one_to_one(self) -> None:
        executor = DuckDBReadOnlyExecutor()
        self.addCleanup(executor.close)
        executor.register_rows("events", ({"id": 1}, {"id": 1}, {"id": 2}))
        executor.register_rows("entities", ({"id": 1}, {"id": 2}))
        many_to_one = JoinAnalyzer(executor).analyze("events", "entities", (("id", "id"),))
        self.assertEqual(many_to_one.cardinality, JoinCardinality.MANY_TO_ONE)

        executor.register_rows("left_unique", ({"id": 1}, {"id": 2}))
        executor.register_rows("right_unique", ({"id": 1}, {"id": 2}))
        one_to_one = JoinAnalyzer(executor).analyze("left_unique", "right_unique", (("id", "id"),))
        self.assertEqual(one_to_one.cardinality, JoinCardinality.ONE_TO_ONE)

    def test_FR_GRAIN_003_join_requires_keys(self) -> None:
        executor = DuckDBReadOnlyExecutor()
        self.addCleanup(executor.close)
        with self.assertRaisesRegex(ValueError, "join-key"):
            JoinAnalyzer(executor).analyze("left", "right", ())


if __name__ == "__main__":
    unittest.main()
