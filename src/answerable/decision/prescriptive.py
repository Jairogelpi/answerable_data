from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Alternative:
    name: str
    expected_utility: float
    uncertainty: float
    feasible: bool = True
    guardrails_pass: bool = True

    @property
    def conservative_utility(self) -> float:
        return self.expected_utility - self.uncertainty


@dataclass(frozen=True, slots=True)
class Recommendation:
    objective: str
    selected: str
    alternatives: tuple[str, ...]
    expected_utility: float
    uncertainty: float
    downside_guardrails: tuple[str, ...]
    reversal_condition: str


class PrescriptiveAssessor:
    def recommend(
        self,
        objective: str,
        alternatives: tuple[Alternative, ...],
        *,
        constraints: tuple[str, ...],
        downside_guardrails: tuple[str, ...],
        reversal_condition: str,
    ) -> Recommendation:
        if not objective or len(alternatives) < 2:
            raise ValueError("objective and at least two alternatives are required")
        if not constraints or not downside_guardrails or not reversal_condition:
            raise ValueError("constraints, guardrails, and reversal condition are required")
        eligible = tuple(
            alternative
            for alternative in alternatives
            if alternative.feasible and alternative.guardrails_pass
        )
        if not eligible:
            raise ValueError("no alternative satisfies constraints and guardrails")
        selected = max(eligible, key=lambda item: (item.conservative_utility, item.name))
        return Recommendation(
            objective,
            selected.name,
            tuple(item.name for item in alternatives),
            selected.expected_utility,
            selected.uncertainty,
            downside_guardrails,
            reversal_condition,
        )
