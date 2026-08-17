# Epistemic Mutation Testing: Testing Whether Analytical Systems Know When to Change Their Mind

**Status:** working paper, not peer-reviewed. Reproducible from this repository.
**Date:** 2026-08-17

## Abstract

An analytical system can compute the right number and still support the
wrong conclusion, if the evidence underneath that conclusion has changed and
the system doesn't notice. We introduce Epistemic Mutation Testing (EMT): a
paired-scenario benchmark that measures whether a system revises a
conclusion correctly when its supporting evidence is deliberately mutated.
We apply EMT to Answerable, a deterministic analytical validity engine, and
to two current LLM coding agents (Claude Sonnet 5, Codex/`gpt-5.6-sol`)
answering the same blind cases. Answerable scores 100% (48/48 paired
transitions, 3 failure classes). Both LLMs are *safe* by our strictest
measure — 0% unsafe `KEEP` — but when evidence is invalidated outright, both
systematically answer `QUALIFY` (soften) instead of `RETRACT` (withdraw):
16/16 and 22/22 of their respective errors on that transition, a
concentration a one-sided exact binomial test rules out as chance at
p = 2.3×10⁻⁸ and p = 3.2×10⁻¹¹. The finding is that these models don't fail
to notice broken evidence — they systematically under-react to it.

## 1. The problem

Data quality tools (Great Expectations, dbt tests) validate that data
matches a schema or a constraint. Model monitoring tools (Evidently) watch
whether a model's inputs or outputs drift. Neither asks the question that
determines whether a conclusion is trustworthy: *given this evidence, is
this specific claim justified, and if the evidence changes, does the
conclusion change with it?*

That second half — updating correctly — is not implied by getting the
answer right once. A system (human or AI) can calculate a correct effect
size on a valid comparison, then fail to notice when a later version of the
same analysis has lost the property that made the comparison valid.

## 2. Definitions

**Analytical validity engine.** A system that, given data and a declared
analysis, determines whether the requested conclusion is *answerable*:
supported by evidence, or blocked by an identified defect (`ANSWERABLE`,
`ANSWERABLE_WITH_ASSUMPTIONS`, or blocked with named findings).

**Epistemic Mutation Testing.** A methodology for the *second* question:
given a baseline analysis and one deliberate mutation to its evidence, does
the system choose the correct transition?

| Action | Required behavior |
| --- | --- |
| `KEEP` | Preserve the conclusion — the change is epistemically irrelevant. |
| `QUALIFY` | Preserve direction, weaken confidence — the effect materially attenuated. |
| `RETRACT` | Withdraw the conclusion — a validity condition the analysis depended on is now broken. |
| `REVERSE` | Change direction — the evidence now points the other way. |

**Unsafe KEEP.** The error that matters most: keeping a conclusion whose
evidence should have forced a `RETRACT` or `REVERSE`. A system with a
nonzero unsafe-`KEEP` rate is actively dangerous — it presents broken
analysis as intact.

**Overreaction.** The opposite failure: changing a conclusion that should
have stayed. A system that scores 0% unsafe `KEEP` by retracting everything
is useless, not safe — overreaction is the check against that trivial
solution.

## 3. Benchmark construction

Twelve scenarios are spread evenly across three **failure classes**, each
destroying a different property by a different mechanism, so a system can't
pass by recognizing one repeated pattern:

| Failure class | Property destroyed | Required blocker |
| --- | --- | --- |
| `causal` | Covariate overlap between treatment arms (positivity) | `positivity_violation` |
| `temporal` | A completed observation window before the analysis cutoff | `immature_cohort` |
| `data_model` | One row per declared unit of analysis (grain) | `duplicate_entities` |

Each scenario has a clean baseline and four mutations, giving the four
required transitions above (`irrelevant_noise`→`KEEP`,
`effect_attenuation`→`QUALIFY`, `evidence_invalidation`→`RETRACT`,
`outcome_reversal`→`REVERSE`): **12 scenarios × 4 mutations = 48 paired
tests.**

For Answerable, the oracle is not hand-authored: baseline and mutated data
are executed through the real `AssessmentRunner`, and the transition is
classified from the resulting verdict, blockers, and observed effect size
(`src/answerable/mutation_benchmark.py`).

### 3.1 Freezing

A benchmark that can be revised after seeing results proves nothing. The
case set is frozen as `emt-v1`
([`benchmarks/releases/emt-v1/`](../../benchmarks/releases/emt-v1/)):
`manifest.json`, `cases.jsonl` (blind — no expected actions), `oracle.json`,
`protocol.md`, and `SHA256SUMS` with a release hash over the checksums.
`cases.jsonl` is self-contained: full evidence summaries, ready to hand to
an external agent, no separate data-generation step required to reproduce.

**Update, post-publication:** a second frozen release, `emt-v2`
([`benchmarks/releases/emt-v2/`](../../benchmarks/releases/emt-v2/)),
extends the case set from 3 failure classes to 7 (adding `predictive`,
`statistical`, `metric_semantics`, `missingness` — 112 pairs total), each
backed by its own detector in the engine rather than a scenario-specific
shortcut. The §5 results below are unchanged and remain scored against
`emt-v1`, exactly as run; they have not yet been re-run against `emt-v2`. Per
the freeze rule, `emt-v1` stays published and immutable — `emt-v2` is a new
release, not a revision of this one.

## 4. External-agent protocol

Three independently identified agents are meant to run every case twice
(3 × 2 × 48 = 288 decisions); a run is scored per-agent regardless of
completeness, but the full-matrix comparison requires all three
(`evaluate_agent_matrix`, `scripts/score_mutation_agents.py`).

`scripts/run_agent_harness.py` drives `claude` and `codex` through their
CLIs (spending the operator's own subscription, no API key) and Gemini
through the public API. Getting a genuine judgment out of a coding-agent CLI
required stripping its default persona (`--system-prompt`,
`--setting-sources ""`) and running from a directory outside the repository
— without both, the CLI treats the task as "explore this codebase" and asks
for "the real data" instead of judging the evidence given in the prompt.
Both agents are told, verbatim: *"The evidence given is complete and final;
do not ask for additional data, files, or context."*

## 5. Results (2026-08-17)

Full data, raw prompts/responses, and reproduction steps:
[`benchmarks/epistemic_mutations/results/2026-08-17-claude-codex/`](../../benchmarks/epistemic_mutations/results/2026-08-17-claude-codex/).

| Agent | Accuracy | Unsafe KEEP | Overreaction | Consistency |
| --- | --- | --- | --- | --- |
| Answerable | 100.0% | 0.0% | 0.0% | 100.0% |
| Codex (`gpt-5.6-sol`) | 83.3% | 0.0% | 0.0% | 100.0% |
| Claude (`claude-sonnet-5`) | 77.1% | 0.0% | 0.0% | 95.8% |

Gemini is not included: the free tier's 20-requests/day cap on
`gemini-2.5-flash` exhausted mid-run, and `gemini-2.5-flash-lite` with
proper throttling still lost most calls to persistent rate limiting.
Reporting a run at n≈20 alongside two complete n=96 runs would overstate
its precision; it is future work, not a claim made here.

### 5.1 The systematic failure: RETRACT on evidence invalidation

Restricted to the 12 `evidence_invalidation` scenarios (24 cases per agent,
correct action `RETRACT`):

| Agent | RETRACT correct | Dominant wrong answer | P(that concentration \| chance)\* |
| --- | --- | --- | --- |
| Answerable | 24/24 | — | — |
| Codex | 8/24 | `QUALIFY`, 16 of 16 errors | 2.32 × 10⁻⁸ |
| Claude | 2/24 | `QUALIFY`, 22 of 22 errors | 3.19 × 10⁻¹¹ |

\* One-sided exact binomial test, computed with `math.comb` (no external
statistics dependency,
[`scripts/build_emt_results.py:_binomial_upper_tail`](../../scripts/build_emt_results.py)).
Null hypothesis: a wrong answer is drawn uniformly among the three
non-`RETRACT` actions (p = 1/3) — "wrong, but not systematically wrong in
one direction." Both models clear this by many orders of magnitude.

This is the paper's central claim, stated precisely: **it is not that these
models fail to notice broken evidence.** Unsafe `KEEP` is 0% for both — they
never present a conclusion as intact once its evidence is gone. **The
failure is directional and specific: they systematically under-correct,
softening a conclusion that should have been withdrawn.** `QUALIFY` is the
plausible-sounding wrong answer — "the effect is probably still there, just
weaker" — when the correct answer is "the comparison that produced this
number is no longer valid at all."

## 6. Threats to validity

- **Sample size.** n=24 per model per failure-class-restricted analysis, 12
  independent scenarios. The *direction* of the effect is statistically
  decisive (p < 10⁻⁷ for both models); the *precision of the rate itself*
  (2/24 vs. 8/24) is not — a larger case set per failure class would narrow
  that, not the directional finding.
- **Two models, one prompt style.** Both Claude and Codex saw an identical
  evidence-summary format and judge system prompt. Whether the QUALIFY-bias
  generalizes across prompt designs, or to models this study didn't reach
  (Gemini, GPT via direct API, others), is untested. That the pattern held
  across two different providers under the same prompt is suggestive, not
  proof of universality.
- **Coding-agent CLIs, not raw model endpoints.** Claude and Codex were
  accessed through their CLI tooling with the default persona stripped
  (§4). A direct API call to the same underlying model, or a different
  agent harness, could behave differently — though the persona-stripping
  was specifically to approximate a raw judgment call.
- **Synthetic scenarios.** All 12 scenarios use generated data with the
  same shape (two-group comparison, 12 rows/arm). Real-world analytical
  failures are messier; this benchmark isolates one mechanism per failure
  class deliberately, which is a feature for attribution and a limitation
  for ecological validity.
- **Answerable's 100% is not free of construction bias.** Answerable's own
  blocker logic was written by the same team that designed the mutation
  scenarios, using the same three failure-class mechanisms
  (`positivity_violation`, `immature_cohort`, `duplicate_entities`). A
  deterministic system built to detect exactly these three breaks scoring
  100% on exactly these three breaks is expected, not independently
  surprising — the interesting comparison is the LLM columns, not
  Answerable's own score in isolation.

## 7. Reproducing

```bash
python scripts/run_agent_harness.py --agents claude,codex --repetitions 2 \
  --output runs/emt-agents
python scripts/build_emt_results.py \
  --llm-decisions runs/emt-agents/decisions.jsonl \
  --output runs/emt-results
```

`build_emt_results.py` re-derives Answerable's decisions from the live
engine (not a cached score) each time it runs, so the comparison is always
computed fresh against whatever code is checked out.

## 8. Related work

- **Great Expectations, dbt tests** — validate that data conforms to
  declared constraints. Orthogonal: a dataset can pass every expectation
  and still not support a specific causal or comparative claim.
- **Evidently, model-monitoring tools** — detect drift in model inputs or
  outputs over time. Answer "did something change," not "does the evidence
  still support this specific conclusion."
- **Mutation testing (software engineering)** — the naming and paired
  baseline/mutant structure are deliberately borrowed from code mutation
  testing, applied to evidence instead of code: the "mutant" here is a
  changed dataset, and "killing" it means correctly changing the
  conclusion, not detecting a bug.

## 9. Limitations of this document

This is a working paper written and reproduced within this repository, not
independently reviewed. Treat its statistical claims (§5.1) as sound given
the stated null and sample; treat its broader claims (§1, abstract) as a
thesis supported by one benchmark run, not a general finding about LLMs.
