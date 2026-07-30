from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb

from answerable.domain.serialization import fingerprint
from answerable.ingestion.errors import InvalidSource, UnsupportedFormat
from answerable.ingestion.models import (
    ColumnProfile,
    DataAssetSnapshot,
    DataProfile,
    SampleResult,
    SourceFormat,
)

_FORMATS = {
    ".csv": SourceFormat.CSV,
    ".jsonl": SourceFormat.JSONL,
    ".ndjson": SourceFormat.JSONL,
    ".parquet": SourceFormat.PARQUET,
}


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class FileInspector:
    def __init__(self) -> None:
        self._connection = duckdb.connect()

    def close(self) -> None:
        self._connection.close()

    def inspect(self, path: Path | str) -> DataAssetSnapshot:
        source = self._validate(path)
        source_format = self._format(source)
        source_fingerprint = self._hash_file(source)
        relation = self._reader(source, source_format)
        description = self._connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        row_count = self._scalar_int(f"SELECT count(*) FROM {relation}")
        columns: list[ColumnProfile] = []
        for row in description:
            name = str(row[0])
            physical_type = str(row[1])
            identifier = _quote_identifier(name)
            counts = self._connection.execute(
                f"SELECT count(*) - count({identifier}), "
                f"count(DISTINCT {identifier}) FROM {relation}"
            ).fetchone()
            if counts is None:
                raise InvalidSource("profiling query returned no result")
            nulls, distinct = counts
            columns.append(
                ColumnProfile(
                    name=name,
                    physical_type=physical_type,
                    null_count=int(nulls),
                    distinct_count=int(distinct),
                )
            )
        profile = DataProfile(row_count=row_count, sampled=False, columns=tuple(columns))
        return DataAssetSnapshot(
            asset_id=f"asset_{source_fingerprint[:24]}",
            path=str(source),
            source_format=source_format,
            fingerprint=source_fingerprint,
            byte_size=source.stat().st_size,
            row_count=row_count,
            profile=profile,
        )

    def sample(self, path: Path | str, *, size: int, seed: int) -> SampleResult:
        if size <= 0:
            raise ValueError("sample size must be positive")
        snapshot = self.inspect(path)
        source = Path(snapshot.path)
        relation = self._reader(source, snapshot.source_format)
        names = tuple(column.name for column in snapshot.profile.columns)
        if not names:
            rows: tuple[dict[str, object], ...] = ()
        else:
            values = ", ".join(
                f"coalesce(cast({_quote_identifier(name)} AS VARCHAR), '<NULL>')" for name in names
            )
            query = (
                f"SELECT * FROM {relation} "
                f"ORDER BY hash(concat_ws('|', {values}, {_sql_string(str(seed))})) "
                f"LIMIT {int(size)}"
            )
            cursor = self._connection.execute(query)
            records = cursor.fetchall()
            rows = tuple(dict(zip(names, record, strict=True)) for record in records)
        return SampleResult(
            rows=rows,
            requested_size=size,
            seed=seed,
            input_fingerprint=snapshot.fingerprint,
            ordering_fingerprint=fingerprint(
                {"input_fingerprint": snapshot.fingerprint, "seed": seed}
            ),
        )

    @staticmethod
    def _validate(path: Path | str) -> Path:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise InvalidSource(f"source is not a readable file: {source}")
        return source

    @staticmethod
    def _format(path: Path) -> SourceFormat:
        try:
            return _FORMATS[path.suffix.lower()]
        except KeyError as error:
            raise UnsupportedFormat(f"unsupported file extension: {path.suffix}") from error

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _reader(path: Path, source_format: SourceFormat) -> str:
        escaped = _sql_string(str(path))
        if source_format is SourceFormat.CSV:
            return f"read_csv_auto({escaped}, sample_size=-1)"
        if source_format is SourceFormat.JSONL:
            return f"read_json_auto({escaped}, format='newline_delimited')"
        if source_format is SourceFormat.PARQUET:
            return f"read_parquet({escaped})"
        raise UnsupportedFormat(source_format)

    def _scalar_int(self, sql: str) -> int:
        row = self._connection.execute(sql).fetchone()
        if row is None:
            raise InvalidSource("scalar query returned no result")
        return int(row[0])
