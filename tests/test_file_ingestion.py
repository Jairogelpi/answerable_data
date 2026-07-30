from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import duckdb

from answerable.ingestion.errors import InvalidSource, UnsupportedFormat
from answerable.ingestion.files import FileInspector
from answerable.ingestion.models import ColumnProfile, DataProfile, SourceFormat


class FileIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.inspector = FileInspector()

    def tearDown(self) -> None:
        self.inspector.close()
        self.tempdir.cleanup()

    def _write_csv(self) -> Path:
        path = self.root / "customers.csv"
        path.write_text(
            "customer_id,country,revenue\n1,ES,10.5\n2,PT,20.0\n3,ES,\n",
            encoding="utf-8",
        )
        return path

    def test_FR_DATA_003_file_snapshot_has_content_fingerprint(self) -> None:
        path = self._write_csv()
        first = self.inspector.inspect(path)
        second = self.inspector.inspect(path)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(len(first.fingerprint), 64)
        self.assertEqual(first.byte_size, path.stat().st_size)

    def test_phase_4_profiles_csv_with_full_data_provenance(self) -> None:
        snapshot = self.inspector.inspect(self._write_csv())
        self.assertEqual(snapshot.source_format, SourceFormat.CSV)
        self.assertEqual(snapshot.row_count, 3)
        self.assertFalse(snapshot.profile.sampled)
        profiles = {column.name: column for column in snapshot.profile.columns}
        self.assertEqual(profiles["customer_id"].null_count, 0)
        self.assertEqual(profiles["customer_id"].distinct_count, 3)
        self.assertEqual(profiles["revenue"].null_count, 1)

    def test_FR_DATA_005_sampling_is_deterministic_and_recorded(self) -> None:
        path = self._write_csv()
        first = self.inspector.sample(path, size=2, seed=42)
        second = self.inspector.sample(path, size=2, seed=42)
        different = self.inspector.sample(path, size=2, seed=7)
        self.assertEqual(first.rows, second.rows)
        self.assertEqual(first.input_fingerprint, second.input_fingerprint)
        self.assertEqual(first.seed, 42)
        self.assertNotEqual(first.ordering_fingerprint, different.ordering_fingerprint)

    def test_phase_4_reads_jsonl_and_parquet(self) -> None:
        jsonl = self.root / "events.jsonl"
        jsonl.write_text(
            "\n".join(
                json.dumps(row)
                for row in (
                    {"event_id": 1, "kind": "open"},
                    {"event_id": 2, "kind": "click"},
                )
            ),
            encoding="utf-8",
        )
        parquet = self.root / "events.parquet"
        connection = duckdb.connect()
        connection.execute(
            "COPY (SELECT 1 AS event_id, 'open' AS kind UNION ALL SELECT 2, 'click') "
            f"TO '{parquet.as_posix()}' (FORMAT PARQUET)"
        )
        connection.close()

        self.assertEqual(self.inspector.inspect(jsonl).source_format, SourceFormat.JSONL)
        self.assertEqual(self.inspector.inspect(parquet).source_format, SourceFormat.PARQUET)
        self.assertEqual(self.inspector.inspect(parquet).row_count, 2)

    def test_phase_4_rejects_unknown_extension(self) -> None:
        path = self.root / "customers.xml"
        path.write_text("<rows/>", encoding="utf-8")
        with self.assertRaises(UnsupportedFormat):
            self.inspector.inspect(path)

    def test_phase_4_rejects_missing_sources_and_invalid_sample_size(self) -> None:
        with self.assertRaises(InvalidSource):
            self.inspector.inspect(self.root / "missing.csv")
        with self.assertRaisesRegex(ValueError, "positive"):
            self.inspector.sample(self._write_csv(), size=0, seed=1)

    def test_phase_4_profile_models_reject_negative_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "negative"):
            ColumnProfile("id", "BIGINT", -1, 0)
        with self.assertRaisesRegex(ValueError, "negative"):
            DataProfile(-1, False, ())


if __name__ == "__main__":
    unittest.main()
