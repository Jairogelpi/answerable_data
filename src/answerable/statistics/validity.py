from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from answerable.quality.models import Finding, Severity


class CorrectionMethod(StrEnum):
    BONFERRONI = "bonferroni"
    BENJAMINI_HOCHBERG = "benjamini_hochberg"


@dataclass(frozen=True, slots=True)
class StatisticalResult:
    estimate: float
    standard_error: float
    confidence_interval: tuple[float, float]
    effect_size: float
    p_value: float
    adjusted_p_value: float
    power: float
    minimum_detectable_effect: float
    findings: tuple[Finding, ...]
    allowed_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]


class StatisticalAssessor:
    def assess_mean_difference(
        self,
        treatment: tuple[float, ...],
        control: tuple[float, ...],
        *,
        alpha: float = 0.05,
        comparisons: int = 1,
        correction: CorrectionMethod = CorrectionMethod.BONFERRONI,
        target_power: float = 0.8,
    ) -> StatisticalResult:
        if len(treatment) < 2 or len(control) < 2:
            raise ValueError("each group requires at least two observations")
        if not 0 < alpha < 1 or not 0 < target_power < 1 or comparisons < 1:
            raise ValueError("alpha, target power, and comparisons are invalid")
        estimate = self._mean(treatment) - self._mean(control)
        variance_t = self._variance(treatment)
        variance_c = self._variance(control)
        standard_error = math.sqrt(variance_t / len(treatment) + variance_c / len(control))
        if standard_error == 0:
            p_value = 0.0 if estimate else 1.0
        else:
            z_score = abs(estimate / standard_error)
            p_value = math.erfc(z_score / math.sqrt(2))
        adjusted = self._adjust(p_value, comparisons, correction)
        pooled_deviation = math.sqrt((variance_t + variance_c) / 2)
        effect_size = estimate / pooled_deviation if pooled_deviation else 0.0
        critical = self._normal_quantile(1 - alpha / (2 * comparisons))
        lower, upper = estimate - critical * standard_error, estimate + critical * standard_error
        mde = (critical + self._normal_quantile(target_power)) * standard_error
        power = self._approximate_power(abs(estimate), standard_error, critical)
        findings: list[Finding] = []
        if power < target_power:
            findings.append(
                Finding(
                    "insufficient_power",
                    Severity.BLOCKER,
                    "Observed design power is below the configured target.",
                    observed=power,
                )
            )
        allowed = (f"Estimated mean difference: {estimate:.6g}.",)
        forbidden: tuple[str, ...] = ()
        if adjusted >= alpha:
            forbidden = ("The data prove there is no effect.",)
        return StatisticalResult(
            estimate,
            standard_error,
            (lower, upper),
            effect_size,
            p_value,
            adjusted,
            power,
            mde,
            tuple(findings),
            allowed,
            forbidden,
        )

    @staticmethod
    def adjust_p_values(p_values: tuple[float, ...], method: CorrectionMethod) -> tuple[float, ...]:
        if not p_values or any(not 0 <= value <= 1 for value in p_values):
            raise ValueError("p-values must be non-empty and between zero and one")
        if method is CorrectionMethod.BONFERRONI:
            return tuple(min(1.0, value * len(p_values)) for value in p_values)
        ordered = sorted(enumerate(p_values), key=lambda item: item[1])
        adjusted = [1.0] * len(p_values)
        running = 1.0
        for reverse_rank, (index, value) in enumerate(reversed(ordered), start=1):
            rank = len(p_values) - reverse_rank + 1
            running = min(running, value * len(p_values) / rank)
            adjusted[index] = min(1.0, running)
        return tuple(adjusted)

    @staticmethod
    def assumption_findings(
        *,
        influential_fraction: float,
        subgroup_effects: tuple[float, ...],
        robust_estimate: float | None,
        classical_estimate: float,
    ) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        if influential_fraction > 0.05:
            findings.append(
                Finding(
                    "influential_observations",
                    Severity.WARNING,
                    "Influential observations exceed the configured tolerance.",
                    observed=influential_fraction,
                )
            )
        if subgroup_effects and min(subgroup_effects) < 0 < max(subgroup_effects):
            findings.append(
                Finding(
                    "subgroup_instability",
                    Severity.WARNING,
                    "Effect direction changes across subgroups.",
                )
            )
        if robust_estimate is not None and not math.isclose(
            robust_estimate, classical_estimate, rel_tol=0.2, abs_tol=1e-9
        ):
            findings.append(
                Finding(
                    "robustness_failure",
                    Severity.BLOCKER,
                    "Robust and classical estimates materially disagree.",
                )
            )
        return tuple(findings)

    @staticmethod
    def _mean(values: tuple[float, ...]) -> float:
        return sum(values) / len(values)

    @classmethod
    def _variance(cls, values: tuple[float, ...]) -> float:
        mean = cls._mean(values)
        return sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    @staticmethod
    def _adjust(value: float, comparisons: int, method: CorrectionMethod) -> float:
        return StatisticalAssessor.adjust_p_values((value,) * comparisons, method)[0]

    @staticmethod
    def _approximate_power(effect: float, standard_error: float, critical: float) -> float:
        if standard_error == 0:
            return float(effect > 0)
        noncentral = effect / standard_error
        return max(0.0, min(1.0, 0.5 * math.erfc((critical - noncentral) / math.sqrt(2))))

    @staticmethod
    def _normal_quantile(probability: float) -> float:
        # Acklam rational approximation, deterministic and dependency-free.
        if not 0 < probability < 1:
            raise ValueError("probability must be between zero and one")
        a = (
            -39.6968302866538,
            220.946098424521,
            -275.928510446969,
            138.357751867269,
            -30.6647980661472,
            2.50662827745924,
        )
        b = (
            -54.4760987982241,
            161.585836858041,
            -155.698979859887,
            66.8013118877197,
            -13.2806815528857,
        )
        c = (
            -0.00778489400243029,
            -0.322396458041136,
            -2.40075827716184,
            -2.54973253934373,
            4.37466414146497,
            2.93816398269878,
        )
        d = (0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742)
        if probability < 0.02425:
            q = math.sqrt(-2 * math.log(probability))
            return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
                (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
            )
        if probability > 0.97575:
            return -StatisticalAssessor._normal_quantile(1 - probability)
        q = probability - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / ((((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r) + 1)
        )
