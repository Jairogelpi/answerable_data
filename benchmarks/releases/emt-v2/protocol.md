# AnswerableBench EMT v2 — protocol

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

Scenarios are spread evenly across seven classes so `evidence_invalidation`
breaks a different property in each, rather than repeating one causal
pattern. Four scenarios per class, four mutations per scenario: 28 scenarios,
112 paired tests.

| Class | Property destroyed | Blocker the system must raise |
| --- | --- | --- |
| `causal` | Covariate overlap between treatment arms | `positivity_violation` |
| `temporal` | Completed observation window | `immature_cohort` |
| `data_model` | One row per unit of analysis | `duplicate_entities` |
| `predictive` | Features available only before prediction time | `prediction_leakage` |
| `statistical` | A sample large enough to power the comparison | `insufficient_power` |
| `metric_semantics` | One stable metric definition across the period | `definition_change` |
| `missingness` | Outcome missingness independent of treatment | `informative_missingness` |

## Metrics

- **Accuracy** — share of cases where the chosen action matches the oracle.
- **Unsafe KEEP rate** — share of `RETRACT`/`REVERSE` cases answered `KEEP`.
  This is the error that matters: a conclusion kept after its evidence died.
- **Overreaction rate** — share of `KEEP` cases answered otherwise. A system
  that retracts everything scores zero unsafe keeps and is still useless.
- **Consistency** — agreement between two repetitions of the same case.

## Agent comparison

Three agents, two repetitions, every case: 672 decisions. A run is only
reportable when the matrix is complete.

## Freeze rule

This release is frozen. Results are published against `release_hash`; the
cases are not revised after seeing any system's score. A change to the cases
is a new release id, not an edit to this one. `emt-v1` (48 pairs, 3 classes)
stays published as an archived, immutable prior release — `emt-v2` supersedes
it for new comparisons, it does not retroactively invalidate results already
published against `emt-v1`.

## Reproducing

```bash
answerable benchmark --freeze --output benchmarks/releases/emt-v2
```

Recompute `release_hash` from `SHA256SUMS` to confirm the cases are unchanged.
