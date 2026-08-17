# Epistemic Mutation Testing

Epistemic Mutation Testing (EMT) measures whether a system changes its conclusion when — and only when — the evidence warrants a change.

The benchmark is paired by construction. Every scenario has a clean baseline and four deterministic mutations. The system never receives a hand-authored verdict from the benchmark runner: each baseline and mutation is executed through `AssessmentRunner`, then the transition is classified from the resulting verdict, blockers and observed effect.

<img src="dashboard.svg" alt="AnswerableBench EMT results" width="640">

Regenerate the dashboard after a run:

```bash
answerable benchmark mutations --output runs/epistemic-mutations
python scripts/render_benchmark_dashboard.py runs/epistemic-mutations/mutation_report.json \
  --output benchmarks/epistemic_mutations/dashboard.svg
```

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
| `evidence_invalidation` | Destroy the validity condition the scenario's design depends on. | `RETRACT` |
| `outcome_reversal` | Reverse the sign of the observed group difference while preserving an otherwise valid design. | `REVERSE` |

There are 28 deterministic scenarios and four mutations per scenario: **112 paired mutation tests**.

## Failure classes

A benchmark built on one repeated causal pattern only proves the system detects that pattern. Scenarios are spread evenly across seven classes, so `evidence_invalidation` breaks a different property in each and must be caught by a different check — each backed by a real, unit-tested detector in the engine, not a scenario-specific shortcut:

| Class | Scenarios | Property destroyed | Blocker required |
| --- | --- | --- | --- |
| `causal` | 4 | Covariate overlap between treatment arms | `positivity_violation` |
| `temporal` | 4 | Completed observation window before the cutoff | `immature_cohort` |
| `data_model` | 4 | One row per declared unit of analysis | `duplicate_entities` |
| `predictive` | 4 | Features available only before prediction time | `prediction_leakage` |
| `statistical` | 4 | A sample large enough to power the comparison | `insufficient_power` |
| `metric_semantics` | 4 | One stable metric definition across the period | `definition_change` |
| `missingness` | 4 | Outcome missingness independent of treatment | `informative_missingness` |

Per-class accuracy is reported alongside per-family accuracy and is part of the release gate: passing overall while failing one class does not pass.

Every question run through `AssessmentRunner` gets a blanket statistical-power check, regardless of failure class — a real, not-scenario-specific feature. That means an `effect_attenuation` or `outcome_reversal` mutation *could* legitimately also be underpowered on its own; the benchmark only credits or blames a scenario for the *specific* blocker its class is designed to test (`expected_blocker(failure_class)`), so an incidental power warning on, say, a `causal`-class scenario doesn't get misread as that scenario testing statistical power.

## Run

```bash
answerable benchmark mutations --output runs/epistemic-mutations
```

## Frozen release

Results are only meaningful against a benchmark that cannot be edited after seeing them. `emt-v2` is frozen and hash-addressed:

```bash
answerable benchmark --freeze --output benchmarks/releases/emt-v2
```

This writes `manifest.json`, `cases.jsonl`, `oracle.json`, `protocol.md` and `SHA256SUMS`. The release hash is the digest of `SHA256SUMS`; recomputing it confirms the cases are unchanged. `cases.jsonl` carries no expected actions, so it can be handed to a blind run directly. Revising the cases means publishing a new release id, not editing this one.

[`emt-v1`](../releases/emt-v1/) (48 pairs, 3 classes) stays published as an archived, immutable prior release — it is what the [Claude/Codex comparison](results/2026-08-17-claude-codex/) was run against, and `emt-v2` does not retroactively change those published numbers. `emt-v2` is the current benchmark for any new comparison.

The release gate requires:

- exactly 112 paired tests;
- 100% oracle-action accuracy;
- 0% unsafe `KEEP` decisions on `RETRACT` or `REVERSE` opportunities;
- 0% overreaction on `KEEP` opportunities;
- 100% accuracy in every mutation family and every failure class;
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

A comparative run uses **3 independently identified agents × 2 repetitions × 112 pairs = 672 decisions**. Store the returned actions as JSONL records with this logical schema:

```json
{
  "agent_id": "provider/model-or-agent-id",
  "repetition": 1,
  "pair_id": "emt-causal-01-evidence_invalidation",
  "action": "RETRACT"
}
```

Score the complete matrix:

```bash
python scripts/score_mutation_agents.py runs/emt-agent-results.jsonl \
  --output runs/emt-agent-report.json
```

### Running real agents

`scripts/run_agent_harness.py` drives the frozen `emt-v2` cases through
three independently identified agents: Claude and Codex via their CLIs
(already authenticated on this machine, spending the operator's own
subscription, no API key), and Gemini via the public API (needs
`GEMINI_API_KEY` — free-tier `gemini-2.5-flash` by default):

```bash
export GEMINI_API_KEY=...   # only needed if "gemini" is in --agents
python scripts/run_agent_harness.py \
  --cases benchmarks/releases/emt-v2/cases.jsonl \
  --output runs/emt-agents \
  --agents claude,codex,gemini \
  --repetitions 2
python scripts/score_mutation_agents.py runs/emt-agents/decisions.jsonl
```

It writes `decisions.jsonl` (scoreable directly) and `raw.jsonl` — one record
per call with the full prompt, raw response, resolved model, timestamp,
latency, token usage, cost (where the caller reports it) and the case hash,
so a run is independently auditable.

Two things worth knowing before trusting a run:

- **`evaluate_agent_matrix` requires all three agent slots filled** — 672
  decisions from `claude,codex,gemini` — before `matrix_complete` is `True`.
  Fewer agents or repetitions still score per-agent, but `matrix_complete`
  correctly reports `False` and the release-gate exit code stays reserved.
- **The CLIs are coding-agent shells, not raw model endpoints.** The harness
  strips that persona for a fair judgment call — `claude` runs with
  `--system-prompt` (replacing, not appending to, the default persona) and
  `--setting-sources ""` (no CLAUDE.md/hooks/memory); both agents run from a
  scratch directory outside the repo via `--scratch-dir`. Skipping either
  guard reliably produces "no data given, point me to a file" instead of a
  judgment, because the CLI still believes it's a coding assistant.

The evaluator rejects an incomplete matrix. For each agent it reports:

- paired oracle accuracy;
- unsafe `KEEP` rate on cases that require `RETRACT` or `REVERSE`;
- overreaction rate on cases that require `KEEP`;
- repeat-to-repeat consistency.

The core library exposes `evaluate_agent_matrix(...)` for the same scoring. A result must not be described as an LLM comparison unless all 672 decisions came from actual independent model executions under the blind protocol. Synthetic or heuristic baselines may be useful for tests, but are not LLM evidence.

Note: the [published Claude/Codex comparison](results/2026-08-17-claude-codex/) was run against `emt-v1` (48 pairs, 3 classes), before `emt-v2` existed — it has not yet been re-run against the full 7-class set.

## Why paired mutation testing

Ordinary benchmarks reward a correct final answer. EMT tests the update rule itself. A model that gets a baseline right but refuses to retract after comparison support disappears is epistemically unsafe; a model that changes its conclusion because an irrelevant field changed is unstable. The paired design measures both failure modes directly.
