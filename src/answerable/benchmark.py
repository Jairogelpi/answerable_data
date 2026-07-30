from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    family: str
    expected_verdict: str
    required_findings: frozenset[str]
    critical_causal: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    case_id: str
    verdict: str
    findings: frozenset[str]
    causal_safety_violation: bool = False


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    verdict_accuracy: float
    blocker_recall: float
    causal_safety_violations: int
    release_pass: bool


class BenchmarkRunner:
    REQUIRED_FAMILIES = frozenset(
        {
            "schema_grain",
            "join_explosion",
            "duplicates",
            "missingness",
            "selection_survival",
            "time_censoring",
            "experiments",
            "causal_identification",
            "prediction_leakage",
            "metric_definition",
            "diagnostic_decomposition",
            "fairness_subgroups",
            "prescriptive",
            "prompt_injection",
            "executor_failure",
        }
    )

    def evaluate(
        self,
        cases: tuple[BenchmarkCase, ...],
        observations: tuple[BenchmarkObservation, ...],
        *,
        require_full_families: bool = True,
    ) -> BenchmarkReport:
        if not cases or {case.case_id for case in cases} != {item.case_id for item in observations}:
            raise ValueError("benchmark cases and observations must align")
        families = {case.family for case in cases}
        if require_full_families and not families >= self.REQUIRED_FAMILIES:
            raise ValueError("benchmark family coverage is incomplete")
        observed = {item.case_id: item for item in observations}
        correct = sum(observed[case.case_id].verdict == case.expected_verdict for case in cases)
        required = sum(len(case.required_findings) for case in cases)
        found = sum(len(case.required_findings & observed[case.case_id].findings) for case in cases)
        violations = sum(item.causal_safety_violation for item in observations)
        accuracy = correct / len(cases)
        recall = found / required if required else 1.0
        return BenchmarkReport(
            accuracy, recall, violations, accuracy == 1 and recall == 1 and violations == 0
        )
