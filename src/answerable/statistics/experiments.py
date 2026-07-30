from __future__ import annotations

import math
from dataclasses import dataclass

from answerable.quality.models import Finding, Severity


@dataclass(frozen=True, slots=True)
class ExperimentDesign:
    expected_allocation: tuple[float, ...]
    randomization_unit: str
    analysis_unit: str
    planned_looks: int = 1
    current_look: int = 1
    stopping_rule_declared: bool = True


class ExperimentAssessor:
    def assess(
        self,
        assignments: tuple[int, ...],
        *,
        design: ExperimentDesign,
        exposure_rate: float = 1.0,
        contamination_rate: float = 0.0,
        attrition_rates: tuple[float, ...] = (),
        balance_differences: tuple[float, ...] = (),
        guardrails_pass: bool = True,
        clustered_errors_used: bool = False,
    ) -> tuple[Finding, ...]:
        if len(assignments) != len(design.expected_allocation):
            raise ValueError("assignment and allocation groups must match")
        if not math.isclose(sum(design.expected_allocation), 1.0, abs_tol=1e-9):
            raise ValueError("expected allocation must sum to one")
        findings: list[Finding] = []
        total = sum(assignments)
        if total <= 0:
            raise ValueError("experiment must contain assigned units")
        chi_square = sum(
            (observed - total * expected) ** 2 / (total * expected)
            for observed, expected in zip(assignments, design.expected_allocation, strict=True)
        )
        if chi_square > 10.828:
            findings.append(
                Finding(
                    "sample_ratio_mismatch",
                    Severity.BLOCKER,
                    "Allocation differs materially from the randomized design.",
                    observed=chi_square,
                )
            )
        if exposure_rate < 0.95:
            findings.append(
                Finding("missing_exposure", Severity.BLOCKER, "Exposure logging is incomplete.")
            )
        if contamination_rate > 0.01:
            findings.append(
                Finding(
                    "contamination",
                    Severity.BLOCKER,
                    "Treatment contamination exceeds tolerance.",
                    observed=contamination_rate,
                )
            )
        if attrition_rates and max(attrition_rates) - min(attrition_rates) > 0.02:
            findings.append(
                Finding(
                    "differential_attrition",
                    Severity.BLOCKER,
                    "Attrition differs materially across experiment arms.",
                )
            )
        if balance_differences and max(map(abs, balance_differences)) > 0.1:
            findings.append(
                Finding(
                    "pre_experiment_imbalance",
                    Severity.WARNING,
                    "Standardized pre-experiment imbalance exceeds 0.1.",
                )
            )
        if design.current_look > 1 and (
            design.planned_looks < design.current_look or not design.stopping_rule_declared
        ):
            findings.append(
                Finding(
                    "invalid_sequential_testing",
                    Severity.BLOCKER,
                    "Interim analysis is not covered by a declared stopping rule.",
                )
            )
        if design.randomization_unit != design.analysis_unit and not clustered_errors_used:
            findings.append(
                Finding(
                    "randomization_unit_mismatch",
                    Severity.BLOCKER,
                    "Analysis unit differs from randomization without clustered uncertainty.",
                )
            )
        if not guardrails_pass:
            findings.append(
                Finding(
                    "guardrail_failure", Severity.BLOCKER, "A declared guardrail metric failed."
                )
            )
        return tuple(findings)
