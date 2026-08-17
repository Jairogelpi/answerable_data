# AnswerableBench EMT v1 — protocol

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
