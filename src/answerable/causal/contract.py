from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from answerable.quality.models import Finding, Severity


class IdentificationStrategy(StrEnum):
    RANDOMIZED = "randomized_experiment"
    REGRESSION = "regression_adjustment"
    MATCHING = "matching_weighting"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    INTERRUPTED_TIME_SERIES = "interrupted_time_series"
    REGRESSION_DISCONTINUITY = "regression_discontinuity"
    INSTRUMENTAL_VARIABLE = "instrumental_variable"
    SYNTHETIC_CONTROL = "synthetic_control"
    PANEL = "panel_estimators"


@dataclass(frozen=True, slots=True)
class CausalContract:
    treatment: str
    outcome: str
    population: str
    estimand: str
    strategy: IdentificationStrategy
    adjustment_set: frozenset[str] = frozenset()
    assumptions: tuple[str, ...] = ()
    falsification_checks: tuple[str, ...] = ()
    sensitivity_checks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.treatment, self.outcome, self.population, self.estimand)):
            raise ValueError(
                "causal contract requires treatment, outcome, population, and estimand"
            )
        if self.treatment == self.outcome or self.treatment in self.adjustment_set:
            raise ValueError("invalid treatment/outcome/adjustment relationship")


class Estimator(Protocol):
    def estimate(self, contract: CausalContract) -> float: ...


@dataclass(frozen=True, slots=True)
class CausalAssessment:
    identified: bool
    estimate: float | None
    findings: tuple[Finding, ...]
    refutations: tuple[str, ...]
    forbidden_claims: tuple[str, ...]


class CausalIdentifier:
    def assess(
        self,
        contract: CausalContract,
        estimator: Estimator,
        *,
        randomization_valid: bool = False,
        exchangeability_supported: bool = False,
        parallel_trends_supported: bool = False,
        instrument_valid: bool = False,
        discontinuity_valid: bool = False,
        positivity_supported: bool = True,
    ) -> CausalAssessment:
        identified = positivity_supported and self._strategy_supported(
            contract.strategy,
            randomization_valid=randomization_valid,
            exchangeability_supported=exchangeability_supported,
            parallel_trends_supported=parallel_trends_supported,
            instrument_valid=instrument_valid,
            discontinuity_valid=discontinuity_valid,
        )
        if not identified:
            finding = Finding(
                "causal_identification_failure",
                Severity.BLOCKER,
                "The requested causal estimand is not identified by the available design.",
            )
            return CausalAssessment(
                False,
                None,
                (finding,),
                contract.falsification_checks,
                ("caused", "effect of", "led to", "because of"),
            )
        estimate = estimator.estimate(contract)
        findings: tuple[Finding, ...] = ()
        if not contract.sensitivity_checks:
            findings = (
                Finding(
                    "missing_sensitivity",
                    Severity.WARNING,
                    "No sensitivity analysis was declared for the causal estimate.",
                ),
            )
        return CausalAssessment(True, estimate, findings, contract.falsification_checks, ())

    @staticmethod
    def _strategy_supported(
        strategy: IdentificationStrategy,
        **evidence: bool,
    ) -> bool:
        mapping = {
            IdentificationStrategy.RANDOMIZED: evidence["randomization_valid"],
            IdentificationStrategy.REGRESSION: evidence["exchangeability_supported"],
            IdentificationStrategy.MATCHING: evidence["exchangeability_supported"],
            IdentificationStrategy.DIFFERENCE_IN_DIFFERENCES: evidence["parallel_trends_supported"],
            IdentificationStrategy.INTERRUPTED_TIME_SERIES: evidence["parallel_trends_supported"],
            IdentificationStrategy.REGRESSION_DISCONTINUITY: evidence["discontinuity_valid"],
            IdentificationStrategy.INSTRUMENTAL_VARIABLE: evidence["instrument_valid"],
            IdentificationStrategy.SYNTHETIC_CONTROL: evidence["parallel_trends_supported"],
            IdentificationStrategy.PANEL: evidence["exchangeability_supported"],
        }
        return mapping[strategy]
