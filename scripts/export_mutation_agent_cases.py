from __future__ import annotations

import argparse
import json
from pathlib import Path

from answerable.mutation_benchmark import (
    benchmark_pairs,
    benchmark_scenarios,
    blind_evidence,
    blind_question,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blind EMT pairs for external agents.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scenarios = {scenario.scenario_id: scenario for scenario in benchmark_scenarios()}
    records: list[dict[str, object]] = []
    for pair in benchmark_pairs():
        scenario = scenarios[pair.scenario_id]
        question, previous = blind_question(scenario.failure_class)
        records.append(
            {
                "pair_id": pair.pair_id,
                "question": question,
                "previous_conclusion": previous,
                "baseline_evidence": blind_evidence(scenario, None),
                "mutated_evidence": blind_evidence(scenario, pair.family),
                "allowed_actions": ["KEEP", "QUALIFY", "RETRACT", "REVERSE"],
                "instruction": (
                    "Choose exactly one action for how the previous conclusion should change "
                    "after seeing the mutated evidence. Return only the action token."
                ),
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"exported {len(records)} blind mutation pairs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
