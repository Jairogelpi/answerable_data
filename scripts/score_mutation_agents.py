from __future__ import annotations

import argparse
import json
from pathlib import Path

from answerable.mutation_benchmark import AgentDecision, MutationAction, evaluate_agent_matrix


def _load(path: Path) -> tuple[AgentDecision, ...]:
    decisions: list[AgentDecision] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        try:
            decisions.append(
                AgentDecision(
                    agent_id=str(payload["agent_id"]),
                    repetition=int(payload["repetition"]),
                    pair_id=str(payload["pair_id"]),
                    action=MutationAction(str(payload["action"])),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid decision on line {line_number}: {exc}") from exc
    return tuple(decisions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score 3-agent x 2-repeat EMT decisions.")
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = evaluate_agent_matrix(_load(args.results))
    payload = {
        "pair_count": report.pair_count,
        "decision_count": report.decision_count,
        "matrix_complete": report.matrix_complete,
        "agents": [
            {
                "agent_id": item.agent_id,
                "accuracy": item.accuracy,
                "unsafe_keep_rate": item.unsafe_keep_rate,
                "overreaction_rate": item.overreaction_rate,
                "consistency": item.consistency,
            }
            for item in report.agents
        ],
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report.matrix_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
