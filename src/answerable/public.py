from __future__ import annotations

from dataclasses import dataclass

from answerable.evidence.verdict import FindingInput, VerdictEngine, VerdictResult
from answerable.warrants.service import WarrantIssuer, WarrantRecord


@dataclass(frozen=True, slots=True)
class AssessmentPolicy:
    policy_id: str = "default"
    require_repairability: bool = True


def assess(
    findings: tuple[FindingInput, ...], *, policy: AssessmentPolicy | None = None
) -> VerdictResult:
    del policy
    return VerdictEngine().decide(findings)


def verify_warrant(record: WarrantRecord, secret: bytes | None = None) -> bool:
    return WarrantIssuer.verify(record, secret)
