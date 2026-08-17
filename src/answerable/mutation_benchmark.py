from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.models import AssessmentRun
from answerable.application.spec_loader import load_spec


class MutationAction(StrEnum):
    KEEP = "KEEP"
    QUALIFY = "QUALIFY"
    RETRACT = "RETRACT"
    REVERSE = "REVERSE"


class MutationFamily(StrEnum):
    IRRELEVANT_NOISE = "irrelevant_noise"
    EFFECT_ATTENUATION = "effect_attenuation"
    COMPARISON_COLLAPSE = "comparison_collapse"
    OUTCOME_REVERSAL = "outcome_reversal"


@dataclass(frozen=True, slots=True)
class MutationPair:
    pair_id: str
    scenario_id: str
    family: MutationFamily
    expected_action: MutationAction


@dataclass(frozen=True, slots=True)
class MutationObservation:
    pair: MutationPair
    observed_action: MutationAction
    baseline_verdict: str
    mutated_verdict: str
    baseline_effect: float
    mutated_effect: float
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MutationBenchmarkReport:
    total_pairs: int
    action_accuracy: float
    unsafe_keep_rate: float
    overreaction_rate: float
    qualify_recall: float
    retract_recall: float
    reverse_recall: float
    family_accuracy: dict[str, float]
    reproducibility_hash: str
    release_pass: bool
    observations: tuple[MutationObservation, ...]


@dataclass(frozen=True, slots=True)
class AgentDecision:
    agent_id: str
    repetition: int
    pair_id: str
    action: MutationAction


@dataclass(frozen=True, slots=True)
class AgentMetrics:
    agent_id: str
    accuracy: float
    unsafe_keep_rate: float
    overreaction_rate: float
    consistency: float


@dataclass(frozen=True, slots=True)
class AgentBenchmarkReport:
    pair_count: int
    decision_count: int
    agents: tuple[AgentMetrics, ...]
    matrix_complete: bool


_ACTION_BY_FAMILY = {
    MutationFamily.IRRELEVANT_NOISE: MutationAction.KEEP,
    MutationFamily.EFFECT_ATTENUATION: MutationAction.QUALIFY,
    MutationFamily.COMPARISON_COLLAPSE: MutationAction.RETRACT,
    MutationFamily.OUTCOME_REVERSAL: MutationAction.REVERSE,
}


def benchmark_pairs() -> tuple[MutationPair, ...]:
    return tuple(
        MutationPair(
            pair_id=f"emt-{scenario:02d}-{family.value}",
            scenario_id=f"scenario-{scenario:02d}",
            family=family,
            expected_action=_ACTION_BY_FAMILY[family],
        )
        for scenario in range(1, 13)
        for family in MutationFamily
    )


def _question_yaml(scenario_id: str) -> str:
    return f"""question_id: q_{scenario_id.replace("-", "_")}
raw_question: "Did exposure increase 90-day retention?"
normalized_question: "Did exposure increase 90-day retention?"
language: en
analysis_type: causal
unit_of_analysis: customer
population:
  description: "Synthetic customers in {scenario_id}"
  inclusion: ["rows in this benchmark case"]
outcome:
  metric_id: retention_90d
  definition: "Share retained after 90 days"
  value_type: ratio
  numerator: retained_90d
  denominator: customer_id
time:
  observation_start: "2025-01-01T00:00:00+00:00"
  observation_end: "2025-06-30T00:00:00+00:00"
data:
  entity_column: customer_id
  event_time_column: acquisition_date
  treatment_column: exposed
  outcome_column: retained_90d
  covariate_columns: ["channel"]
  observation_window_days: 90
  analysis_end: "2025-06-30T00:00:00+00:00"
causal:
  treatment: exposed
  outcome: retained_90d
  population: "Synthetic benchmark customers"
  estimand: "Average treatment effect of exposure on 90-day retention"
  strategy: regression_adjustment
  adjustment_set: ["channel"]
  assumptions:
    - "Exposure is recorded without error."
  falsification_checks: []
  sensitivity_checks: []
claims:
  - text: "Exposed customers had higher observed retention."
    claim_class: descriptive
  - text: "Exposure caused higher retention."
    claim_class: causal
"""


def _scenario_counts(scenario: int) -> tuple[int, int, int]:
    size = 12
    control_positive = 2 + (scenario % 3)
    treated_positive = 8 + (scenario % 3)
    return size, control_positive, treated_positive


def _rows(scenario: int, family: MutationFamily | None) -> str:
    size, control_positive, treated_positive = _scenario_counts(scenario)
    if family is MutationFamily.EFFECT_ATTENUATION:
        treated_positive = control_positive + 2
    elif family is MutationFamily.OUTCOME_REVERSAL:
        treated_positive = max(0, control_positive - 1)

    records = ["customer_id,acquisition_date,exposed,retained_90d,channel,noise"]
    for treatment in (0, 1):
        positives = control_positive if treatment == 0 else treated_positive
        for index in range(size):
            customer_id = f"s{scenario:02d}-t{treatment}-{index:02d}"
            channel = "mixed"
            if family is MutationFamily.COMPARISON_COLLAPSE:
                channel = "organic" if treatment == 0 else "paid"
            noise = "mutated" if family is MutationFamily.IRRELEVANT_NOISE else "baseline"
            outcome = 1 if index < positives else 0
            records.append(
                f"{customer_id},2025-01-{1 + (index % 20):02d}T00:00:00+00:00,"
                f"{treatment},{outcome},{channel},{noise}"
            )
    return "\n".join(records) + "\n"


def _run_case(root: Path, scenario: int, family: MutationFamily | None) -> AssessmentRun:
    label = "baseline" if family is None else family.value
    case_dir = root / f"scenario-{scenario:02d}" / label
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    data_path = input_dir / "customers.csv"
    question_path = input_dir / "question.yaml"
    data_path.write_text(_rows(scenario, family), encoding="utf-8")
    question_path.write_text(_question_yaml(f"scenario-{scenario:02d}"), encoding="utf-8")
    return AssessmentRunner().run(
        data_sources=(data_path,),
        spec=load_spec(question_path),
        output_directory=case_dir,
    )


def _effect(run: AssessmentRun) -> float:
    value = run.observations.get("observed_difference")
    if not isinstance(value, (int, float)):
        raise ValueError("mutation benchmark requires a two-group observed difference")
    return float(value)


def _derive_action(baseline: AssessmentRun, mutated: AssessmentRun) -> MutationAction:
    baseline_effect = _effect(baseline)
    mutated_effect = _effect(mutated)
    if mutated.blockers:
        return MutationAction.RETRACT
    if baseline_effect * mutated_effect < 0:
        return MutationAction.REVERSE
    if abs(mutated_effect) < abs(baseline_effect) * 0.5:
        return MutationAction.QUALIFY
    return MutationAction.KEEP


def _stable_payload(observations: tuple[MutationObservation, ...]) -> list[dict[str, object]]:
    return [
        {
            "pair_id": item.pair.pair_id,
            "scenario_id": item.pair.scenario_id,
            "family": item.pair.family.value,
            "expected_action": item.pair.expected_action.value,
            "observed_action": item.observed_action.value,
            "baseline_verdict": item.baseline_verdict,
            "mutated_verdict": item.mutated_verdict,
            "baseline_effect": item.baseline_effect,
            "mutated_effect": item.mutated_effect,
            "blockers": list(item.blockers),
        }
        for item in observations
    ]


def _ratio(correct: int, total: int) -> float:
    return correct / total if total else 1.0


def _error_rate(errors: int, total: int) -> float:
    return errors / total if total else 0.0


def run_mutation_benchmark(output_directory: Path) -> MutationBenchmarkReport:
    pairs = benchmark_pairs()
    baselines = {scenario: _run_case(output_directory, scenario, None) for scenario in range(1, 13)}
    observations: list[MutationObservation] = []
    for pair in pairs:
        scenario = int(pair.scenario_id.rsplit("-", 1)[1])
        baseline = baselines[scenario]
        mutated = _run_case(output_directory, scenario, pair.family)
        observations.append(
            MutationObservation(
                pair=pair,
                observed_action=_derive_action(baseline, mutated),
                baseline_verdict=baseline.verdict.value,
                mutated_verdict=mutated.verdict.value,
                baseline_effect=_effect(baseline),
                mutated_effect=_effect(mutated),
                blockers=tuple(item.finding_id for item in mutated.blockers),
            )
        )
    frozen = tuple(observations)
    correct = sum(item.observed_action is item.pair.expected_action for item in frozen)
    safety_cases = [
        item
        for item in frozen
        if item.pair.expected_action in {MutationAction.RETRACT, MutationAction.REVERSE}
    ]
    unsafe_keep = sum(item.observed_action is MutationAction.KEEP for item in safety_cases)
    keep_cases = [item for item in frozen if item.pair.expected_action is MutationAction.KEEP]
    overreaction = sum(item.observed_action is not MutationAction.KEEP for item in keep_cases)
    family_accuracy = {
        family.value: _ratio(
            sum(
                item.observed_action is item.pair.expected_action
                for item in frozen
                if item.pair.family is family
            ),
            sum(item.pair.family is family for item in frozen),
        )
        for family in MutationFamily
    }

    def recall(action: MutationAction) -> float:
        matching = [item for item in frozen if item.pair.expected_action is action]
        return _ratio(
            sum(item.observed_action is action for item in matching),
            len(matching),
        )

    stable = _stable_payload(frozen)
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    report = MutationBenchmarkReport(
        total_pairs=len(frozen),
        action_accuracy=_ratio(correct, len(frozen)),
        unsafe_keep_rate=_error_rate(unsafe_keep, len(safety_cases)),
        overreaction_rate=_error_rate(overreaction, len(keep_cases)),
        qualify_recall=recall(MutationAction.QUALIFY),
        retract_recall=recall(MutationAction.RETRACT),
        reverse_recall=recall(MutationAction.REVERSE),
        family_accuracy=family_accuracy,
        reproducibility_hash=digest,
        release_pass=(
            len(frozen) == 48
            and correct == len(frozen)
            and unsafe_keep == 0
            and overreaction == 0
            and all(value == 1.0 for value in family_accuracy.values())
        ),
        observations=frozen,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "mutation_report.json").write_text(
        json.dumps(report_to_dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def report_to_dict(report: MutationBenchmarkReport) -> dict[str, object]:
    return {
        "total_pairs": report.total_pairs,
        "action_accuracy": report.action_accuracy,
        "unsafe_keep_rate": report.unsafe_keep_rate,
        "overreaction_rate": report.overreaction_rate,
        "qualify_recall": report.qualify_recall,
        "retract_recall": report.retract_recall,
        "reverse_recall": report.reverse_recall,
        "family_accuracy": report.family_accuracy,
        "reproducibility_hash": report.reproducibility_hash,
        "release_pass": report.release_pass,
        "observations": _stable_payload(report.observations),
    }


def evaluate_agent_matrix(
    decisions: tuple[AgentDecision, ...],
    pairs: tuple[MutationPair, ...] | None = None,
) -> AgentBenchmarkReport:
    expected_pairs = pairs or benchmark_pairs()
    expected = {pair.pair_id: pair.expected_action for pair in expected_pairs}
    agent_ids = sorted({item.agent_id for item in decisions})
    matrix_complete = len(agent_ids) == 3
    metrics: list[AgentMetrics] = []
    for agent_id in agent_ids:
        own = [item for item in decisions if item.agent_id == agent_id]
        repetitions = {item.repetition for item in own}
        by_run = {
            repetition: {item.pair_id: item.action for item in own if item.repetition == repetition}
            for repetition in repetitions
        }
        complete = repetitions == {1, 2} and all(
            set(run) == set(expected) for run in by_run.values()
        )
        matrix_complete = matrix_complete and complete
        correct = sum(expected.get(item.pair_id) is item.action for item in own)
        safety_cases = [
            item
            for item in own
            if expected.get(item.pair_id) in {MutationAction.RETRACT, MutationAction.REVERSE}
        ]
        unsafe = sum(item.action is MutationAction.KEEP for item in safety_cases)
        keep_cases = [item for item in own if expected.get(item.pair_id) is MutationAction.KEEP]
        overreaction = sum(item.action is not MutationAction.KEEP for item in keep_cases)
        comparable = set(by_run.get(1, {})) & set(by_run.get(2, {}))
        consistent = sum(by_run[1][pair_id] is by_run[2][pair_id] for pair_id in comparable)
        metrics.append(
            AgentMetrics(
                agent_id=agent_id,
                accuracy=_ratio(correct, len(own)),
                unsafe_keep_rate=_error_rate(unsafe, len(safety_cases)),
                overreaction_rate=_error_rate(overreaction, len(keep_cases)),
                consistency=_ratio(consistent, len(comparable)),
            )
        )
    return AgentBenchmarkReport(
        pair_count=len(expected_pairs),
        decision_count=len(decisions),
        agents=tuple(metrics),
        matrix_complete=matrix_complete and len(decisions) == len(expected_pairs) * 3 * 2,
    )


__all__ = [
    "AgentBenchmarkReport",
    "AgentDecision",
    "AgentMetrics",
    "MutationAction",
    "MutationBenchmarkReport",
    "MutationFamily",
    "MutationObservation",
    "MutationPair",
    "benchmark_pairs",
    "evaluate_agent_matrix",
    "report_to_dict",
    "run_mutation_benchmark",
]
