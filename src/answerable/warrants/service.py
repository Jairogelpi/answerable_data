from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class AnalysisPlan:
    question: str
    estimand: str
    datasets: tuple[str, ...]
    transformations: tuple[str, ...]
    metric: str
    method: str
    diagnostics: tuple[str, ...]
    uncertainty: str
    sensitivity_checks: tuple[str, ...]
    visualization: str
    reporting_language: str
    acceptance_criteria: tuple[str, ...]
    executable_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.question or not self.estimand or not self.datasets or not self.method:
            raise ValueError("analysis plan requires question, estimand, data, and method")


@dataclass(frozen=True, slots=True)
class WarrantRecord:
    warrant_id: str
    version: int
    canonical_json: str
    content_hash: str
    issued_at: datetime
    signer: str | None = None
    signature: str | None = None
    supersedes: str | None = None

    @property
    def data(self) -> Mapping[str, object]:
        return MappingProxyType(json.loads(self.canonical_json))


class WarrantIssuer:
    REQUIRED = (
        "identity",
        "question",
        "decision_context",
        "verdict",
        "executive_explanation",
        "allowed_claims",
        "forbidden_claims",
        "decisive_evidence",
        "assumptions",
        "limitations",
        "data_quality_relevance",
        "minimum_evidence_plan",
        "permitted_analysis",
        "provenance",
        "reproducibility_manifest",
        "approvals",
        "supersession_status",
    )

    def issue(
        self,
        warrant_id: str,
        version: int,
        payload: Mapping[str, object],
        *,
        signer: str | None = None,
        secret: bytes | None = None,
        supersedes: str | None = None,
    ) -> WarrantRecord:
        if set(payload) != set(self.REQUIRED):
            raise ValueError("warrant payload must contain every canonical section exactly")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        signature = None
        if signer or secret:
            if not signer or not secret:
                raise ValueError("signer and secret must be supplied together")
            signature = hmac.new(secret, content_hash.encode(), hashlib.sha256).hexdigest()
        return WarrantRecord(
            warrant_id,
            version,
            canonical,
            content_hash,
            datetime.now(UTC),
            signer,
            signature,
            supersedes,
        )

    @staticmethod
    def verify(record: WarrantRecord, secret: bytes | None = None) -> bool:
        actual = hashlib.sha256(record.canonical_json.encode()).hexdigest()
        if not hmac.compare_digest(actual, record.content_hash):
            return False
        if record.signature is None:
            return secret is None
        if secret is None:
            return False
        expected = hmac.new(secret, record.content_hash.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, record.signature)

    @staticmethod
    def export(record: WarrantRecord, format_name: str) -> str:
        data = json.loads(record.canonical_json)
        if format_name == "json":
            return record.canonical_json
        if format_name == "markdown":
            return "\n".join(
                f"## {key.replace('_', ' ').title()}\n\n{json.dumps(value, ensure_ascii=False)}"
                for key, value in data.items()
            )
        if format_name == "html":
            body = "".join(
                f"<section><h2>{key.replace('_', ' ').title()}</h2>"
                f"<pre>{json.dumps(value, ensure_ascii=False)}</pre></section>"
                for key, value in data.items()
            )
            return f"<!doctype html><html><body>{body}</body></html>"
        raise ValueError("unsupported warrant export format")
