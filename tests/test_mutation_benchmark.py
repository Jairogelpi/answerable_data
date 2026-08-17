from __future__ import annotations

from pathlib import Path

from answerable.mutation_benchmark import (
    AgentDecision,
    FailureClass,
    MutationAction,
    MutationFamily,
    benchmark_pairs,
    benchmark_scenarios,
    evaluate_agent_matrix,
    expected_blocker,
    materialize_case,
    run_mutation_benchmark,
)


def test_manifest_has_28_scenarios_and_112_pairs_across_seven_classes() -> None:
    pairs = benchmark_pairs()

    assert len(pairs) == 112
    assert len({pair.scenario_id for pair in pairs}) == 28
    assert {pair.failure_class for pair in pairs} == set(FailureClass)
    assert len(FailureClass) == 7
    assert {pair.family for pair in pairs} == set(MutationFamily)
    assert {pair.expected_action for pair in pairs} == set(MutationAction)
    assert len({pair.pair_id for pair in pairs}) == 112


def test_scenarios_spread_evenly_across_failure_classes() -> None:
    scenarios = benchmark_scenarios()

    assert len(scenarios) == 28
    assert {scenario.failure_class for scenario in scenarios} == set(FailureClass)
    for failure_class in FailureClass:
        matching = [item for item in scenarios if item.failure_class is failure_class]
        assert len(matching) == 4
        assert len({item.variant for item in matching}) == 4


def test_mutation_benchmark_executes_runner_and_passes_release_gate(tmp_path: Path) -> None:
    report = run_mutation_benchmark(tmp_path / "bench")

    assert report.total_pairs == 112
    assert report.action_accuracy == 1.0
    assert report.unsafe_keep_rate == 0.0
    assert report.overreaction_rate == 0.0
    assert report.qualify_recall == 1.0
    assert report.retract_recall == 1.0
    assert report.reverse_recall == 1.0
    assert set(report.family_accuracy.values()) == {1.0}
    assert set(report.class_accuracy.values()) == {1.0}
    assert len(report.class_accuracy) == 7
    assert report.release_pass
    assert len(report.reproducibility_hash) == 64
    assert (tmp_path / "bench" / "mutation_report.json").is_file()
    assert all(item.baseline_verdict == "ANSWERABLE" for item in report.observations)
    invalidated = [
        item
        for item in report.observations
        if item.pair.family is MutationFamily.EVIDENCE_INVALIDATION
    ]
    assert len(invalidated) == 28
    # Each failure class must be blocked by its own mechanism, not a shared one.
    for item in invalidated:
        assert expected_blocker(item.pair.failure_class) in item.blockers


def test_materialize_case_writes_real_files_the_engine_accepts(tmp_path: Path) -> None:
    from answerable.application.assessment_runner import AssessmentRunner
    from answerable.application.spec_loader import load_spec

    scenario = benchmark_scenarios()[0]
    data_path = materialize_case(tmp_path, scenario, MutationFamily.EVIDENCE_INVALIDATION)

    assert data_path.is_file()
    question_path = data_path.parent / "question.yaml"
    assert question_path.is_file()
    # Not just files on disk -- the real engine accepts and blocks them,
    # same as run_mutation_benchmark's own internal case generation.
    run = AssessmentRunner().run(
        data_sources=(data_path,),
        spec=load_spec(question_path),
        output_directory=tmp_path / "out",
    )
    assert expected_blocker(scenario.failure_class) in {item.finding_id for item in run.blockers}


def test_mutation_benchmark_is_reproducible_across_directories(tmp_path: Path) -> None:
    first = run_mutation_benchmark(tmp_path / "first")
    second = run_mutation_benchmark(tmp_path / "second")

    assert first.reproducibility_hash == second.reproducibility_hash
    assert first.action_accuracy == second.action_accuracy


def test_agent_matrix_requires_three_agents_two_repetitions_and_all_pairs() -> None:
    pairs = benchmark_pairs()
    decisions = tuple(
        AgentDecision(
            agent_id=agent,
            repetition=repetition,
            pair_id=pair.pair_id,
            action=pair.expected_action,
        )
        for agent in ("agent-a", "agent-b", "agent-c")
        for repetition in (1, 2)
        for pair in pairs
    )
    report = evaluate_agent_matrix(decisions, pairs)

    assert report.matrix_complete
    assert report.decision_count == 672
    assert all(item.accuracy == 1.0 for item in report.agents)
    assert all(item.unsafe_keep_rate == 0.0 for item in report.agents)
    assert all(item.overreaction_rate == 0.0 for item in report.agents)
    assert all(item.consistency == 1.0 for item in report.agents)


def test_agent_metrics_surface_unsafe_keep_and_incomplete_matrix() -> None:
    pair = next(
        pair for pair in benchmark_pairs() if pair.expected_action is MutationAction.RETRACT
    )
    report = evaluate_agent_matrix(
        (
            AgentDecision("agent-a", 1, pair.pair_id, MutationAction.KEEP),
            AgentDecision("agent-a", 2, pair.pair_id, MutationAction.RETRACT),
        ),
        (pair,),
    )

    assert not report.matrix_complete
    assert report.agents[0].accuracy == 0.5
    assert report.agents[0].unsafe_keep_rate == 0.5
    assert report.agents[0].overreaction_rate == 0.0
    assert report.agents[0].consistency == 0.0


def test_agent_metrics_surface_overreaction_without_inventing_safety_errors() -> None:
    pair = next(pair for pair in benchmark_pairs() if pair.expected_action is MutationAction.KEEP)
    report = evaluate_agent_matrix(
        (
            AgentDecision("agent-a", 1, pair.pair_id, MutationAction.QUALIFY),
            AgentDecision("agent-a", 2, pair.pair_id, MutationAction.KEEP),
        ),
        (pair,),
    )

    assert report.agents[0].accuracy == 0.5
    assert report.agents[0].unsafe_keep_rate == 0.0
    assert report.agents[0].overreaction_rate == 0.5
    assert report.agents[0].consistency == 0.0
