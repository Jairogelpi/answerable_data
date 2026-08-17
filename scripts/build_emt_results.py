"""Build the final AnswerableBench EMT comparison: Answerable vs LLM agents.

Answerable enters the same comparison as a "4th agent": its own decisions on
whatever benchmark_pairs() currently returns, produced by actually running
run_mutation_benchmark (the deterministic engine) rather than citing its
release-gate score. Two repetitions are recorded for parity with the LLM
protocol, even though a deterministic engine's second run is identical by
construction -- that determinism is the point, not a shortcut.

--oracle MUST match the release the --llm-decisions pair_ids were scored
against (emt-v1's 48 pair_ids differ from emt-v2's 112) -- a mismatch fails
with a clear KeyError, not a silently wrong score, but pass the right one.

The interesting statistical claim isn't just "the model didn't retract" --
it's that the wrong answers aren't spread randomly across the other three
actions. A binomial test against a uniform-among-wrong-actions null (p=1/3)
quantifies that directly, with no external stats dependency: for the sample
sizes here (n<=24 per class), math.comb computes the exact tail probability.

Usage:
    python scripts/build_emt_results.py \\
        --llm-decisions runs/emt-v2-agents/decisions.jsonl \\
        --oracle benchmarks/releases/emt-v2/oracle.json \\
        --output runs/emt-v2-results
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from answerable.mutation_benchmark import (
    AgentDecision,
    MutationAction,
    benchmark_pairs,
    evaluate_agent_matrix,
    run_mutation_benchmark,
)


def answerable_decisions() -> tuple[AgentDecision, ...]:
    """Answerable's own answers on the current benchmark_pairs(), from the real engine."""
    report = run_mutation_benchmark(Path("runs/_answerable_as_agent"))
    decisions = []
    for observation in report.observations:
        for repetition in (1, 2):
            decisions.append(
                AgentDecision(
                    agent_id="answerable",
                    repetition=repetition,
                    pair_id=observation.pair.pair_id,
                    action=observation.observed_action,
                )
            )
    return tuple(decisions)


def _load_decisions(paths: list[Path]) -> list[AgentDecision]:
    decisions: list[AgentDecision] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            decisions.append(
                AgentDecision(
                    agent_id=str(payload["agent_id"]),
                    repetition=int(payload["repetition"]),
                    pair_id=str(payload["pair_id"]),
                    action=MutationAction(str(payload["action"])),
                )
            )
    return decisions


def _binomial_upper_tail(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p), computed exactly via math.comb."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def _confusion_on_evidence_invalidation(
    agent_id: str, decisions: list[AgentDecision], oracle: dict[str, str]
) -> dict[str, object]:
    rows = [d for d in decisions if d.agent_id == agent_id and "evidence_invalidation" in d.pair_id]
    n = len(rows)
    correct = sum(1 for d in rows if oracle[d.pair_id] == d.action.value)
    wrong = [d for d in rows if oracle[d.pair_id] != d.action.value]
    wrong_by_action: dict[str, int] = {}
    for d in wrong:
        wrong_by_action[d.action.value] = wrong_by_action.get(d.action.value, 0) + 1
    # Among wrong answers, is one specific action (typically QUALIFY)
    # over-represented relative to a uniform draw among the 3 non-RETRACT
    # actions? p=1/3 is the null: "wrong, but no particular direction."
    dominant_action, dominant_count = (
        max(wrong_by_action.items(), key=lambda item: item[1]) if wrong_by_action else (None, 0)
    )
    p_value = _binomial_upper_tail(dominant_count, len(wrong), 1 / 3) if wrong else None
    return {
        "agent_id": agent_id,
        "n": n,
        "retract_correct": correct,
        "retract_rate": correct / n if n else None,
        "wrong_by_action": wrong_by_action,
        "dominant_wrong_action": dominant_action,
        "dominant_wrong_count": dominant_count,
        "wrong_total": len(wrong),
        "p_value_dominant_direction": p_value,
    }


def _retract_by_failure_class(
    agent_id: str, decisions: list[AgentDecision], oracle: dict[str, str]
) -> dict[str, dict[str, object]]:
    """RETRACT accuracy on evidence_invalidation, broken out per failure class.

    A single pooled RETRACT rate across every class can hide a real,
    interesting split -- e.g. an agent that retracts perfectly on one
    mechanism (say, prediction leakage) but almost never on the others.
    Pooling would average that into "medium accuracy" and lose the finding.
    """
    class_by_pair = {pair.pair_id: pair.failure_class.value for pair in benchmark_pairs()}
    by_class: dict[str, list[AgentDecision]] = {}
    for decision in decisions:
        if decision.agent_id != agent_id or "evidence_invalidation" not in decision.pair_id:
            continue
        by_class.setdefault(class_by_pair[decision.pair_id], []).append(decision)
    return {
        failure_class: {
            "n": len(rows),
            "retract_correct": sum(1 for d in rows if oracle[d.pair_id] == d.action.value),
        }
        for failure_class, rows in sorted(by_class.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Answerable vs LLM EMT comparison.")
    parser.add_argument("--llm-decisions", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--oracle",
        type=Path,
        default=Path("benchmarks/releases/emt-v2/oracle.json"),
        help="Must match the release the --llm-decisions pair_ids were scored against.",
    )
    args = parser.parse_args()

    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))["expected_action"]
    decisions = _load_decisions(args.llm_decisions) + list(answerable_decisions())
    # Keep the newest decision per (agent_id, repetition, pair_id): a rerun
    # (e.g. gemini after the quota fix) legitimately overwrites an older,
    # failed attempt rather than duplicating it into the scored set.
    deduped: dict[tuple[str, int, str], AgentDecision] = {}
    for decision in decisions:
        deduped[(decision.agent_id, decision.repetition, decision.pair_id)] = decision
    decisions = list(deduped.values())

    matrix_report = evaluate_agent_matrix(tuple(decisions))
    agent_ids = sorted({d.agent_id for d in decisions})

    results: dict[str, object] = {
        "agents": {},
        "decision_counts": {
            agent_id: sum(1 for d in decisions if d.agent_id == agent_id) for agent_id in agent_ids
        },
    }
    for metrics in matrix_report.agents:
        results["agents"][metrics.agent_id] = {  # type: ignore[index]
            "accuracy": metrics.accuracy,
            "unsafe_keep_rate": metrics.unsafe_keep_rate,
            "overreaction_rate": metrics.overreaction_rate,
            "consistency": metrics.consistency,
        }
    results["evidence_invalidation_analysis"] = [
        _confusion_on_evidence_invalidation(agent_id, decisions, oracle) for agent_id in agent_ids
    ]
    results["retract_by_failure_class"] = {
        agent_id: _retract_by_failure_class(agent_id, decisions, oracle) for agent_id in agent_ids
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"{'agent':10s} {'accuracy':>9s} {'unsafe':>7s} {'overreact':>10s} {'consist':>8s}")
    for agent_id in agent_ids:
        m = results["agents"].get(agent_id)  # type: ignore[union-attr]
        if not m:
            continue
        print(
            f"{agent_id:10s} {m['accuracy']:9.1%} {m['unsafe_keep_rate']:7.1%} "
            f"{m['overreaction_rate']:10.1%} {m['consistency']:8.1%}"
        )
    print()
    print("evidence_invalidation (should RETRACT):")
    for row in results["evidence_invalidation_analysis"]:  # type: ignore[union-attr]
        dominant = (
            f"{row['dominant_wrong_action']} ({row['dominant_wrong_count']}/{row['wrong_total']})"
        )
        print(
            f"  {row['agent_id']:10s} n={row['n']:2d} retract={row['retract_correct']}/{row['n']} "
            f"dominant_wrong={dominant} p={row['p_value_dominant_direction']}"
        )
    print()
    print("RETRACT by failure class (a pooled rate can hide this split):")
    for agent_id, by_class in results["retract_by_failure_class"].items():  # type: ignore[union-attr]
        print(f"  {agent_id}:")
        for failure_class, row in by_class.items():
            print(f"    {failure_class:20s} {row['retract_correct']}/{row['n']}")
    print(f"\nwrote {args.output / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
