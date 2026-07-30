from __future__ import annotations

from dataclasses import dataclass

from answerable.quality.models import Finding, Severity


@dataclass(frozen=True, slots=True)
class DriverContribution:
    driver: str
    contribution: float
    evidence_strength: str
    causal: bool = False


@dataclass(frozen=True, slots=True)
class DiagnosticAssessment:
    movement: float
    contributions: tuple[DriverContribution, ...]
    residual: float
    findings: tuple[Finding, ...]


class DiagnosticAssessor:
    def decompose(
        self,
        before: float,
        after: float,
        contributions: tuple[DriverContribution, ...],
        *,
        reconciled: bool = True,
        definition_stable: bool = True,
    ) -> DiagnosticAssessment:
        movement = after - before
        residual = movement - sum(item.contribution for item in contributions)
        findings: list[Finding] = []
        if not reconciled or not definition_stable:
            findings.append(
                Finding(
                    "unverified_metric_movement",
                    Severity.BLOCKER,
                    "Metric movement is not comparable across sources or definitions.",
                )
            )
        if abs(residual) > max(abs(movement) * 0.05, 1e-9):
            findings.append(
                Finding(
                    "unexplained_residual",
                    Severity.WARNING,
                    "Additive drivers do not fully reconcile the metric movement.",
                    observed=residual,
                )
            )
        if any(item.causal for item in contributions):
            findings.append(
                Finding(
                    "unsupported_causal_driver",
                    Severity.BLOCKER,
                    "Contribution decomposition cannot establish a causal explanation.",
                )
            )
        return DiagnosticAssessment(movement, contributions, residual, tuple(findings))

    @staticmethod
    def simpsons_paradox(
        aggregate_direction: int, subgroup_directions: tuple[int, ...]
    ) -> tuple[Finding, ...]:
        if subgroup_directions and all(
            direction == -aggregate_direction for direction in subgroup_directions
        ):
            return (
                Finding(
                    "simpsons_paradox",
                    Severity.WARNING,
                    "Aggregate and every subgroup association have opposite directions.",
                ),
            )
        return ()
