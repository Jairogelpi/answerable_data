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
    EVIDENCE_INVALIDATION = "evidence_invalidation"
    OUTCOME_REVERSAL = "outcome_reversal"


class FailureClass(StrEnum):
    """Family of analytical failure a scenario is built to exercise.

    Each class invalidates evidence through a different mechanism, so the
    benchmark measures whether a system revises conclusions across distinct
    kinds of broken analysis rather than one repeated causal pattern.
    """

    CAUSAL = "causal"
    TEMPORAL = "temporal"
    DATA_MODEL = "data_model"


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    failure_class: FailureClass
    variant: str


@dataclass(frozen=True, slots=True)
class MutationPair:
    pair_id: str
    scenario_id: str
    failure_class: FailureClass
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
    class_accuracy: dict[str, float]
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
    MutationFamily.EVIDENCE_INVALIDATION: MutationAction.RETRACT,
    MutationFamily.OUTCOME_REVERSAL: MutationAction.REVERSE,
}

_VARIANTS: dict[FailureClass, tuple[str, ...]] = {
    FailureClass.CAUSAL: (
        "positivity_collapse",
        "channel_confounding",
        "control_arm_shrink",
        "stratum_imbalance",
    ),
    FailureClass.TEMPORAL: (
        "immature_cohort",
        "late_acquisition",
        "cutoff_shift",
        "window_extension",
    ),
    FailureClass.DATA_MODEL: (
        "join_fanout",
        "grain_duplication",
        "entity_alias_collision",
        "repeated_orders",
    ),
}

_BLOCKER_BY_CLASS = {
    FailureClass.CAUSAL: "positivity_violation",
    FailureClass.TEMPORAL: "immature_cohort",
    FailureClass.DATA_MODEL: "duplicate_entities",
}


def benchmark_scenarios() -> tuple[Scenario, ...]:
    return tuple(
        Scenario(
            scenario_id=f"{failure_class.value}-{index:02d}",
            failure_class=failure_class,
            variant=variant,
        )
        for failure_class, variants in _VARIANTS.items()
        for index, variant in enumerate(variants, start=1)
    )


def expected_blocker(failure_class: FailureClass) -> str:
    """Finding a correct system must raise when this class loses its evidence."""
    return _BLOCKER_BY_CLASS[failure_class]


def benchmark_pairs() -> tuple[MutationPair, ...]:
    return tuple(
        MutationPair(
            pair_id=f"emt-{scenario.scenario_id}-{family.value}",
            scenario_id=scenario.scenario_id,
            failure_class=scenario.failure_class,
            family=family,
            expected_action=_ACTION_BY_FAMILY[family],
        )
        for scenario in benchmark_scenarios()
        for family in MutationFamily
    )


_FRAMING: dict[FailureClass, tuple[str, str, str]] = {
    FailureClass.CAUSAL: (
        "Did the campaign increase 90-day retention?",
        "retention_90d",
        "Share of customers retained 90 days after acquisition",
    ),
    FailureClass.TEMPORAL: (
        "Did the onboarding change improve 90-day activation?",
        "activation_90d",
        "Share of accounts active 90 days after signup",
    ),
    FailureClass.DATA_MODEL: (
        "Did the pricing change improve 90-day account survival?",
        "survival_90d",
        "Share of accounts still billing 90 days after the change",
    ),
}


def _question_yaml(scenario: Scenario) -> str:
    question, metric_id, definition = _FRAMING[scenario.failure_class]
    return f"""question_id: q_{scenario.scenario_id.replace("-", "_")}
raw_question: "{question}"
normalized_question: "{question}"
language: en
analysis_type: causal
unit_of_analysis: customer
population:
  description: "Synthetic customers in {scenario.scenario_id} ({scenario.variant})"
  inclusion: ["rows in this benchmark case"]
outcome:
  metric_id: {metric_id}
  definition: "{definition}"
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
  estimand: "Average treatment effect of exposure on {metric_id}"
  strategy: regression_adjustment
  adjustment_set: ["channel"]
  assumptions:
    - "Exposure is recorded without error."
  falsification_checks: []
  sensitivity_checks: []
claims:
  - text: "Exposed customers had higher observed {metric_id}."
    claim_class: descriptive
  - text: "Exposure caused higher {metric_id}."
    claim_class: causal
"""


def _scenario_counts(scenario: Scenario) -> tuple[int, int, int]:
    """Group size and positive counts, varied per scenario so cases are not clones."""
    offset = int(scenario.scenario_id.rsplit("-", 1)[1])
    size = 12
    control_positive = 2 + (offset % 3)
    treated_positive = 8 + (offset % 3)
    return size, control_positive, treated_positive


def _rows(scenario: Scenario, family: MutationFamily | None) -> str:
    """Render one benchmark case.

    The three non-invalidating families move the effect only. Evidence
    invalidation is class-specific: it destroys the property that made the
    scenario's design valid in the first place.
    """
    size, control_positive, treated_positive = _scenario_counts(scenario)
    if family is MutationFamily.EFFECT_ATTENUATION:
        treated_positive = control_positive + 2
    elif family is MutationFamily.OUTCOME_REVERSAL:
        treated_positive = max(0, control_positive - 1)
    invalidated = family is MutationFamily.EVIDENCE_INVALIDATION
    failure_class = scenario.failure_class

    records = ["customer_id,acquisition_date,exposed,retained_90d,channel,noise"]
    for treatment in (0, 1):
        positives = control_positive if treatment == 0 else treated_positive
        for index in range(size):
            customer_id = f"{scenario.scenario_id}-t{treatment}-{index:02d}"
            channel = "mixed"
            acquired = f"2025-01-{1 + (index % 20):02d}T00:00:00+00:00"
            if invalidated and failure_class is FailureClass.CAUSAL:
                # Every stratum now holds a single treatment level.
                channel = "organic" if treatment == 0 else "paid"
            elif invalidated and failure_class is FailureClass.TEMPORAL:
                # Acquired too late to have completed the 90-day window.
                acquired = f"2025-06-{1 + (index % 20):02d}T00:00:00+00:00"
            elif invalidated and failure_class is FailureClass.DATA_MODEL:
                # A join fan-out collapses two entities onto one identifier.
                customer_id = f"{scenario.scenario_id}-t{treatment}-{index // 2:02d}"
            noise = "mutated" if family is MutationFamily.IRRELEVANT_NOISE else "baseline"
            outcome = 1 if index < positives else 0
            records.append(f"{customer_id},{acquired},{treatment},{outcome},{channel},{noise}")
    return "\n".join(records) + "\n"


def blind_evidence(scenario: Scenario, family: MutationFamily | None) -> dict[str, object]:
    """Summarise one case the way an analyst would see it, with no oracle attached.

    Mirrors `_rows` at the level of detail an external agent needs to decide:
    group sizes, the outcome split, whether covariate strata overlap, whether
    observation windows completed, and whether rows still map one-to-one onto
    entities. This is what ships in a frozen release's cases.jsonl.
    """
    size, control_positive, treated_positive = _scenario_counts(scenario)
    if family is MutationFamily.EFFECT_ATTENUATION:
        treated_positive = control_positive + 2
    elif family is MutationFamily.OUTCOME_REVERSAL:
        treated_positive = max(0, control_positive - 1)
    invalidated = family is MutationFamily.EVIDENCE_INVALIDATION
    failure_class = scenario.failure_class

    channels: dict[str, dict[str, int]] = {
        "unexposed": {"mixed": size},
        "exposed": {"mixed": size},
    }
    windows_complete = True
    distinct_entities = size * 2
    if invalidated and failure_class is FailureClass.CAUSAL:
        channels = {"unexposed": {"organic": size}, "exposed": {"paid": size}}
    elif invalidated and failure_class is FailureClass.TEMPORAL:
        windows_complete = False
    elif invalidated and failure_class is FailureClass.DATA_MODEL:
        distinct_entities = size

    return {
        "rows": size * 2,
        "distinct_entities": distinct_entities,
        "outcome_by_exposure": {
            "unexposed": {"positive": control_positive, "total": size},
            "exposed": {"positive": treated_positive, "total": size},
        },
        "acquisition_channel_by_exposure": channels,
        "unmapped_noise_value": "mutated"
        if family is MutationFamily.IRRELEVANT_NOISE
        else "baseline",
        "observation_window_days": 90,
        "all_observation_windows_complete": windows_complete,
    }


def blind_question(failure_class: FailureClass) -> tuple[str, str]:
    """(question, previous_conclusion) an external agent is shown for this class."""
    question, _, definition = _FRAMING[failure_class]
    return question, f"The exposure increased observed {definition.lower()}."


def _run_case(root: Path, scenario: Scenario, family: MutationFamily | None) -> AssessmentRun:
    label = "baseline" if family is None else family.value
    case_dir = root / scenario.scenario_id / label
    input_dir = case_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    data_path = input_dir / "customers.csv"
    question_path = input_dir / "question.yaml"
    data_path.write_text(_rows(scenario, family), encoding="utf-8")
    question_path.write_text(_question_yaml(scenario), encoding="utf-8")
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
            "failure_class": item.pair.failure_class.value,
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
    scenarios = {scenario.scenario_id: scenario for scenario in benchmark_scenarios()}
    baselines = {
        scenario_id: _run_case(output_directory, scenario, None)
        for scenario_id, scenario in scenarios.items()
    }
    observations: list[MutationObservation] = []
    for pair in pairs:
        baseline = baselines[pair.scenario_id]
        mutated = _run_case(output_directory, scenarios[pair.scenario_id], pair.family)
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
    class_accuracy = {
        failure_class.value: _ratio(
            sum(
                item.observed_action is item.pair.expected_action
                for item in frozen
                if item.pair.failure_class is failure_class
            ),
            sum(item.pair.failure_class is failure_class for item in frozen),
        )
        for failure_class in FailureClass
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
        class_accuracy=class_accuracy,
        reproducibility_hash=digest,
        release_pass=(
            len(frozen) == 48
            and correct == len(frozen)
            and unsafe_keep == 0
            and overreaction == 0
            and all(value == 1.0 for value in family_accuracy.values())
            and all(value == 1.0 for value in class_accuracy.values())
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
        "class_accuracy": report.class_accuracy,
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
    "FailureClass",
    "MutationAction",
    "MutationBenchmarkReport",
    "MutationFamily",
    "MutationObservation",
    "MutationPair",
    "Scenario",
    "benchmark_pairs",
    "benchmark_scenarios",
    "blind_evidence",
    "blind_question",
    "evaluate_agent_matrix",
    "expected_blocker",
    "report_to_dict",
    "run_mutation_benchmark",
]
