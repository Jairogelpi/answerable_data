"""Freeze AnswerableBench EMT as a reproducible, hash-addressed release.

A benchmark that can be edited after seeing results proves nothing. This
module writes the case list, the oracle, the protocol and a checksum file to
disk, then derives a single release hash over those checksums. Anyone can
recompute the hash; if it differs, the benchmark was changed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from answerable.mutation_benchmark import (
    FailureClass,
    MutationFamily,
    benchmark_pairs,
    benchmark_scenarios,
    blind_evidence,
    blind_question,
    expected_blocker,
)

RELEASE_ID = "emt-v1"
_ARTIFACTS = ("manifest.json", "cases.jsonl", "oracle.json", "protocol.md")


@dataclass(frozen=True, slots=True)
class BenchmarkRelease:
    release_id: str
    case_count: int
    scenario_count: int
    release_hash: str
    checksums: dict[str, str]


def _cases() -> list[dict[str, object]]:
    """Blind, self-contained cases: enough for an external agent to answer,
    with no expected action attached. The oracle lives in oracle.json only.
    """
    scenarios = {scenario.scenario_id: scenario for scenario in benchmark_scenarios()}
    cases: list[dict[str, object]] = []
    for pair in benchmark_pairs():
        scenario = scenarios[pair.scenario_id]
        question, previous_conclusion = blind_question(scenario.failure_class)
        cases.append(
            {
                "pair_id": pair.pair_id,
                "scenario_id": pair.scenario_id,
                "failure_class": pair.failure_class.value,
                "variant": scenario.variant,
                "mutation_family": pair.family.value,
                "question": question,
                "previous_conclusion": previous_conclusion,
                "baseline_evidence": blind_evidence(scenario, None),
                "mutated_evidence": blind_evidence(scenario, pair.family),
                "allowed_actions": ["KEEP", "QUALIFY", "RETRACT", "REVERSE"],
                "instruction": (
                    "Choose exactly one action for how the previous conclusion should "
                    "change after seeing the mutated evidence. Return only the action token."
                ),
            }
        )
    return cases


def _oracle() -> dict[str, object]:
    """Expected action per case, plus the blocker each failure class must raise.

    Kept separate from cases.jsonl so a blind run can be handed the cases
    without the answers.
    """
    return {
        "expected_action": {pair.pair_id: pair.expected_action.value for pair in benchmark_pairs()},
        "expected_blocker": {
            failure_class.value: expected_blocker(failure_class) for failure_class in FailureClass
        },
    }


def _manifest() -> dict[str, object]:
    pairs = benchmark_pairs()
    scenarios = benchmark_scenarios()
    return {
        "release_id": RELEASE_ID,
        "case_count": len(pairs),
        "scenario_count": len(scenarios),
        "failure_classes": sorted(item.value for item in FailureClass),
        "mutation_families": sorted(item.value for item in MutationFamily),
        "scenarios_per_class": len(scenarios) // len(FailureClass),
        "agent_protocol": {"agents": 3, "repetitions": 2, "decisions": len(pairs) * 3 * 2},
    }


_PROTOCOL = """# AnswerableBench EMT v1 — protocol

## What is measured

Each case is a *pair*: a baseline analysis, and the same analysis after one
mutation of the evidence. The system under test sees both and must choose one
action.

| Action | Meaning |
| --- | --- |
| `KEEP` | The conclusion still holds. |
| `QUALIFY` | The conclusion holds but weaker than before. |
| `RETRACT` | The evidence no longer supports the conclusion. |
| `REVERSE` | The evidence now points the other way. |

## Mutation families

| Family | Expected action |
| --- | --- |
| `irrelevant_noise` | `KEEP` |
| `effect_attenuation` | `QUALIFY` |
| `evidence_invalidation` | `RETRACT` |
| `outcome_reversal` | `REVERSE` |

## Failure classes

Scenarios are spread across classes so `evidence_invalidation` breaks a
different property in each, rather than repeating one causal pattern:

| Class | Property destroyed | Blocker the system must raise |
| --- | --- | --- |
| `causal` | Covariate overlap between treatment arms | `positivity_violation` |
| `temporal` | Completed observation window | `immature_cohort` |
| `data_model` | One row per unit of analysis | `duplicate_entities` |

## Metrics

- **Accuracy** — share of cases where the chosen action matches the oracle.
- **Unsafe KEEP rate** — share of `RETRACT`/`REVERSE` cases answered `KEEP`.
  This is the error that matters: a conclusion kept after its evidence died.
- **Overreaction rate** — share of `KEEP` cases answered otherwise. A system
  that retracts everything scores zero unsafe keeps and is still useless.
- **Consistency** — agreement between two repetitions of the same case.

## Agent comparison

Three agents, two repetitions, every case: 288 decisions. A run is only
reportable when the matrix is complete.

## Freeze rule

This release is frozen. Results are published against `release_hash`; the
cases are not revised after seeing any system's score. A change to the cases
is a new release id, not an edit to this one.

## Reproducing

```bash
answerable benchmark --freeze --output benchmarks/releases/emt-v1
```

Recompute `release_hash` from `SHA256SUMS` to confirm the cases are unchanged.
"""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_benchmark(output_directory: Path) -> BenchmarkRelease:
    output_directory.mkdir(parents=True, exist_ok=True)
    contents = {
        "manifest.json": json.dumps(_manifest(), indent=2, sort_keys=True) + "\n",
        "cases.jsonl": "".join(
            json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n" for case in _cases()
        ),
        "oracle.json": json.dumps(_oracle(), indent=2, sort_keys=True) + "\n",
        "protocol.md": _PROTOCOL,
    }
    checksums = {name: _digest(contents[name]) for name in _ARTIFACTS}
    for name, text in contents.items():
        (output_directory / name).write_text(text, encoding="utf-8", newline="\n")
    sums = "".join(f"{checksums[name]}  {name}\n" for name in _ARTIFACTS)
    (output_directory / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    manifest = _manifest()
    return BenchmarkRelease(
        release_id=RELEASE_ID,
        case_count=int(manifest["case_count"]),  # type: ignore[arg-type]
        scenario_count=int(manifest["scenario_count"]),  # type: ignore[arg-type]
        release_hash=_digest(sums),
        checksums=checksums,
    )


def verify_release(directory: Path) -> bool:
    """True when every artifact on disk still matches its recorded checksum."""
    sums_path = directory / "SHA256SUMS"
    if not sums_path.is_file():
        return False
    recorded: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        recorded[name] = digest
    if set(recorded) != set(_ARTIFACTS):
        return False
    return all(
        (directory / name).is_file()
        and _digest((directory / name).read_text(encoding="utf-8")) == digest
        for name, digest in recorded.items()
    )


__all__ = ["RELEASE_ID", "BenchmarkRelease", "freeze_benchmark", "verify_release"]
