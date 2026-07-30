from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from answerable.domain.models import Verdict
from answerable.evidence.claims import ClaimContext, ClaimLinter


class Repairability(StrEnum):
    RECOVERABLE = "recoverable"
    DESIGN_IMPOSSIBLE = "design_impossible"
    POLICY_FORBIDDEN = "policy_forbidden"


@dataclass(frozen=True, slots=True)
class FindingInput:
    finding_id: str
    category: str
    severity: str
    message: str
    affects_all_claims: bool = False
    repairability: Repairability | None = None


@dataclass(frozen=True, slots=True)
class VerdictResult:
    verdict: Verdict
    decisive_findings: tuple[FindingInput, ...]
    allowed_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]


class VerdictEngine:
    def decide(
        self,
        findings: tuple[FindingInput, ...],
        *,
        claims: tuple[tuple[str, ClaimContext], ...] = (),
    ) -> VerdictResult:
        blockers = tuple(item for item in findings if item.severity in {"blocker", "fatal"})
        if any(item.repairability is None for item in blockers):
            raise ValueError("every blocker requires repairability")
        verdict = self._precedence(findings)
        allowed: list[str] = []
        forbidden: list[str] = []
        linter = ClaimLinter()
        for claim, context in claims:
            if linter.lint(claim, context):
                forbidden.append(claim)
            else:
                allowed.append(claim)
        return VerdictResult(verdict, blockers or findings, tuple(allowed), tuple(forbidden))

    @staticmethod
    def _precedence(findings: tuple[FindingInput, ...]) -> Verdict:
        categories = {item.category for item in findings if item.severity in {"blocker", "fatal"}}
        if categories & {"execution_fatal", "schema_fatal", "security_fatal"}:
            return Verdict.ASSESSMENT_INCOMPLETE
        if "data_integrity" in categories and any(item.affects_all_claims for item in findings):
            return Verdict.DATA_INTEGRITY_FAILURE
        if "misleading_question" in categories:
            return Verdict.MISLEADING_QUESTION
        if "identification" in categories:
            return Verdict.FUNDAMENTALLY_UNIDENTIFIABLE
        if "missing_evidence" in categories:
            return Verdict.NOT_ANSWERABLE_YET
        if "power" in categories:
            return Verdict.INSUFFICIENT_POWER
        if "partial" in categories:
            return Verdict.PARTIALLY_ANSWERABLE
        if any(item.category == "assumption" for item in findings):
            return Verdict.ANSWERABLE_WITH_ASSUMPTIONS
        return Verdict.ANSWERABLE


@dataclass(frozen=True, slots=True)
class RepairItem:
    missing_information: str
    why_it_matters: str
    retrospective: bool
    collection_method: str
    required_grain: str
    required_population: str
    minimum_time_window: str
    sample_size_target: int | None
    expected_verdict_effect: str
    cost: int
    priority: int
    alternative_question: str


class RepairPlanGenerator:
    def minimal(self, candidates: tuple[RepairItem, ...]) -> tuple[RepairItem, ...]:
        recoverable = tuple(
            item for item in candidates if item.retrospective or item.collection_method
        )
        if not recoverable:
            return ()
        return (
            min(recoverable, key=lambda item: (item.priority, item.cost, item.missing_information)),
        )
