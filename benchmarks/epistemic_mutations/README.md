# Epistemic Mutation Testing

Epistemic Mutation Testing (EMT) measures whether a system changes its conclusion when — and only when — the evidence warrants a change.

The benchmark is paired by construction. Every scenario has a clean baseline and four deterministic mutations. The system never receives a hand-authored verdict from the benchmark runner: each baseline and mutation is executed through `AssessmentRunner`, then the transition is classified from the resulting verdict, blockers and observed effect.

## Oracle actions

| Action | Required behavior |
| --- | --- |
| `KEEP` | Preserve the conclusion because the changed information is epistemically irrelevant. |
| `QUALIFY` | Preserve direction but weaken the conclusion because the evidential magnitude materially attenuated. |
| `RETRACT` | Withdraw the conclusion because a validity condition is broken. |
| `REVERSE` | Change direction because the evidence now supports the opposite directional conclusion. |

## Mutation families

| Family | Mutation | Oracle |
| --- | --- | --- |
| `irrelevant_noise` | Change an unmapped noise field while keeping all analytical evidence fixed. | `KEEP` |
| `effect_attenuation` | Reduce the observed treatment/outcome difference to less than half its baseline magnitude without reversing sign. | `QUALIFY` |
| `comparison_collapse` | Make treatment perfectly determined by the adjustment stratum, destroying positivity. | `RETRACT` |
| `outcome_reversal` | Reverse the sign of the observed group difference while preserving an otherwise valid design. | `REVERSE` |

There are 12 deterministic scenarios and four mutations per scenario: **48 paired mutation tests**.

## Run

```bash
answerable benchmark mutations --output runs/epistemic-mutations
```

The release gate requires:

- exactly 48 paired tests;
- 100% oracle-action accuracy;
- 0% unsafe `KEEP` decisions on `RETRACT` or `REVERSE` opportunities;
- 0% overreaction on `KEEP` opportunities;
- 100% accuracy in every mutation family;
- deterministic reproduction of the same semantic report hash independent of output directory.

`mutation_report.json` contains every pair, expected transition, observed transition, baseline/mutated verdicts, effect sizes and blockers.

## External-agent protocol

LLM comparisons are deliberately separated from the deterministic release gate. Model output is nondeterministic and must not make package releases flaky.

Export the blind evidence pairs:

```bash
python scripts/export_mutation_agent_cases.py \
  --output runs/emt-agent-cases.jsonl
```

The exporter intentionally omits the oracle action. `pair_id` is harness metadata and contains the mutation-family name; **do not include `pair_id` in the prompt sent to the evaluated model**. The model should receive only the question, previous conclusion, baseline evidence, mutated evidence, allowed action tokens and instruction.

A comparative run uses **3 independently identified agents × 2 repetitions × 48 pairs = 288 decisions**. Store the returned actions as JSONL records with this logical schema:

```json
{
  "agent_id": "provider/model-or-agent-id",
  "repetition": 1,
  "pair_id": "emt-01-comparison_collapse",
  "action": "RETRACT"
}
```

Score the complete matrix:

```bash
python scripts/score_mutation_agents.py runs/emt-agent-results.jsonl \
  --output runs/emt-agent-report.json
```

The evaluator rejects an incomplete matrix. For each agent it reports:

- paired oracle accuracy;
- unsafe `KEEP` rate on cases that require `RETRACT` or `REVERSE`;
- overreaction rate on cases that require `KEEP`;
- repeat-to-repeat consistency.

The core library exposes `evaluate_agent_matrix(...)` for the same scoring. A result must not be described as an LLM comparison unless all 288 decisions came from actual independent model executions under the blind protocol. Synthetic or heuristic baselines may be useful for tests, but are not LLM evidence.

## Why paired mutation testing

Ordinary benchmarks reward a correct final answer. EMT tests the update rule itself. A model that gets a baseline right but refuses to retract after comparison support disappears is epistemically unsafe; a model that changes its conclusion because an irrelevant field changed is unstable. The paired design measures both failure modes directly.
