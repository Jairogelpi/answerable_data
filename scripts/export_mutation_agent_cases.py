from __future__ import annotations

import argparse
import json
from pathlib import Path

from answerable.mutation_benchmark import MutationFamily, benchmark_pairs


def _evidence(scenario: int, family: MutationFamily | None) -> dict[str, object]:
    size = 12
    control_positive = 2 + (scenario % 3)
    treated_positive = 8 + (scenario % 3)
    if family is MutationFamily.EFFECT_ATTENUATION:
        treated_positive = control_positive + 2
    elif family is MutationFamily.OUTCOME_REVERSAL:
        treated_positive = max(0, control_positive - 1)

    if family is MutationFamily.COMPARISON_COLLAPSE:
        channels = {
            "unexposed": {"organic": size},
            "exposed": {"paid": size},
        }
    else:
        channels = {
            "unexposed": {"mixed": size},
            "exposed": {"mixed": size},
        }
    noise = "mutated" if family is MutationFamily.IRRELEVANT_NOISE else "baseline"
    return {
        "rows": size * 2,
        "retained_90d": {
            "unexposed": {"retained": control_positive, "total": size},
            "exposed": {"retained": treated_positive, "total": size},
        },
        "acquisition_channel_by_exposure": channels,
        "unmapped_noise_value": noise,
        "observation_window_days": 90,
        "all_observation_windows_complete": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blind EMT pairs for external agents.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records: list[dict[str, object]] = []
    for pair in benchmark_pairs():
        scenario = int(pair.scenario_id.rsplit("-", 1)[1])
        records.append(
            {
                "pair_id": pair.pair_id,
                "question": "Did exposure increase 90-day retention?",
                "previous_conclusion": "Exposure increased 90-day retention.",
                "baseline_evidence": _evidence(scenario, None),
                "mutated_evidence": _evidence(scenario, pair.family),
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
