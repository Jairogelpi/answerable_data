from __future__ import annotations

import argparse
import json
from pathlib import Path

from answerable.mutation_benchmark import (
    FailureClass,
    MutationFamily,
    Scenario,
    benchmark_pairs,
    benchmark_scenarios,
)

_QUESTION = {
    FailureClass.CAUSAL: (
        "Did the campaign increase 90-day retention?",
        "The campaign increased 90-day retention.",
    ),
    FailureClass.TEMPORAL: (
        "Did the onboarding change improve 90-day activation?",
        "The onboarding change improved 90-day activation.",
    ),
    FailureClass.DATA_MODEL: (
        "Did the pricing change improve 90-day account survival?",
        "The pricing change improved 90-day account survival.",
    ),
}


def _evidence(scenario: Scenario, family: MutationFamily | None) -> dict[str, object]:
    """Summarise one case the way an analyst would see it, without the oracle.

    Mirrors the row generation in `answerable.mutation_benchmark`: the three
    non-invalidating families move the effect only, while evidence
    invalidation breaks the property specific to the scenario's class.
    """
    offset = int(scenario.scenario_id.rsplit("-", 1)[1])
    size = 12
    control_positive = 2 + (offset % 3)
    treated_positive = 8 + (offset % 3)
    if family is MutationFamily.EFFECT_ATTENUATION:
        treated_positive = control_positive + 2
    elif family is MutationFamily.OUTCOME_REVERSAL:
        treated_positive = max(0, control_positive - 1)

    invalidated = family is MutationFamily.EVIDENCE_INVALIDATION
    channels: dict[str, dict[str, int]] = {
        "unexposed": {"mixed": size},
        "exposed": {"mixed": size},
    }
    windows_complete = True
    distinct_entities = size * 2
    if invalidated and scenario.failure_class is FailureClass.CAUSAL:
        channels = {"unexposed": {"organic": size}, "exposed": {"paid": size}}
    elif invalidated and scenario.failure_class is FailureClass.TEMPORAL:
        windows_complete = False
    elif invalidated and scenario.failure_class is FailureClass.DATA_MODEL:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Export blind EMT pairs for external agents.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scenarios = {scenario.scenario_id: scenario for scenario in benchmark_scenarios()}
    records: list[dict[str, object]] = []
    for pair in benchmark_pairs():
        scenario = scenarios[pair.scenario_id]
        question, previous = _QUESTION[scenario.failure_class]
        records.append(
            {
                "pair_id": pair.pair_id,
                "question": question,
                "previous_conclusion": previous,
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
