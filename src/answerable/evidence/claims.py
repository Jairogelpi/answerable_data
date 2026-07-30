from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ClaimClass(StrEnum):
    DESCRIPTIVE = "descriptive"
    ASSOCIATION = "association"
    PREDICTIVE = "predictive"
    CAUSAL = "causal"
    DIAGNOSTIC = "diagnostic"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True, slots=True)
class ClaimContext:
    claim_class: ClaimClass
    population: str | None
    period: str | None
    baseline: float | None = None
    causal_gate: bool = False
    subgroup_reliable: bool = True
    decision_id: str | None = None


class ClaimLinter:
    _CAUSAL = re.compile(r"\b(caused|causes|effect of|led to|because of)\b", re.I)

    def lint(self, claim: str, context: ClaimContext) -> tuple[str, ...]:
        violations: list[str] = []
        if self._CAUSAL.search(claim) and (
            context.claim_class is not ClaimClass.CAUSAL or not context.causal_gate
        ):
            violations.append("causal_language_without_identification")
        if not context.population:
            violations.append("population_omitted")
        if not context.period:
            violations.append("period_omitted")
        if re.search(r"\b(no effect|no difference)\b", claim, re.I):
            violations.append("absence_claim_from_nonsignificance")
        if (
            re.search(r"\b(relative|percent increase|% increase)\b", claim, re.I)
            and context.baseline is None
        ):
            violations.append("relative_change_without_baseline")
        if "subgroup" in claim.casefold() and not context.subgroup_reliable:
            violations.append("unreliable_subgroup_claim")
        if context.claim_class is ClaimClass.RECOMMENDATION and not context.decision_id:
            violations.append("recommendation_without_decision")
        return tuple(violations)
