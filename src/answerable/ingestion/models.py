from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceFormat(StrEnum):
    CSV = "csv"
    JSONL = "jsonl"
    PARQUET = "parquet"


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    name: str
    physical_type: str
    null_count: int
    distinct_count: int

    def __post_init__(self) -> None:
        if self.null_count < 0 or self.distinct_count < 0:
            raise ValueError("profile counts cannot be negative")


@dataclass(frozen=True, slots=True)
class DataProfile:
    row_count: int
    sampled: bool
    columns: tuple[ColumnProfile, ...]

    def __post_init__(self) -> None:
        if self.row_count < 0:
            raise ValueError("row_count cannot be negative")


@dataclass(frozen=True, slots=True)
class DataAssetSnapshot:
    asset_id: str
    path: str
    source_format: SourceFormat
    fingerprint: str
    byte_size: int
    row_count: int
    profile: DataProfile


@dataclass(frozen=True, slots=True)
class SampleResult:
    rows: tuple[dict[str, object], ...]
    requested_size: int
    seed: int
    input_fingerprint: str
    ordering_fingerprint: str
