# AnswerableBench EMT — run 2026-08-17 (emt-v2, Claude, Codex)

Real agent decisions against the frozen `emt-v2` case set
([`benchmarks/releases/emt-v2/`](../../../releases/emt-v2/)), produced by
[`scripts/run_agent_harness.py`](../../../../scripts/run_agent_harness.py)
and scored by
[`scripts/build_emt_results.py`](../../../../scripts/build_emt_results.py)
against `emt-v2/oracle.json`.

This supersedes the earlier
[2026-08-17-claude-codex](../2026-08-17-claude-codex/) run, which was
against `emt-v1` (48 pairs, 3 failure classes) and is kept published as-is
per the freeze rule. This run covers all 112 pairs across 7 failure
classes, and the extra classes change the story: the failure isn't
uniform across mechanisms.

## What ran

| Agent | Model | Decisions | Protocol |
| --- | --- | --- | --- |
| Claude | `claude-sonnet-5` | 224/224 | 112 cases × 2 repetitions |
| Codex | `gpt-5.6-sol` | 224/224 | 112 cases × 2 repetitions |
| Answerable | deterministic engine | 224/224 | run twice for protocol parity; identical both times |

Full audit trail in `raw.jsonl` (prompt, response, model, timestamp,
latency, tokens, cost, case hash per call); `decisions.jsonl` is the
schema `evaluate_agent_matrix` reads. Gemini is not included — not
attempted this run; see the `emt-v1` write-up for why its free tier
doesn't sustain a full run without dedicated throttling work.

## Overall

```
agent       accuracy  unsafe  overreact  consist
answerable    100.0%    0.0%       0.0%   100.0%
claude         79.0%    0.0%       0.0%    99.1%
codex          60.7%    0.0%       0.0%    96.4%
```

Both models remain safe by the strictest measure: **0% unsafe KEEP** across
all 112 pairs. Neither ever keeps a conclusion once its evidence is broken.

## The real finding: RETRACT accuracy is not uniform across mechanisms

Pooled across all 7 classes, RETRACT accuracy on `evidence_invalidation`
(n=56 per agent) is 9/56 for Claude and 17/56 for Codex — similar in shape
to the `emt-v1` finding. But pooling hides the actual story:

| Failure class | Answerable | Claude | Codex |
| --- | --- | --- | --- |
| `predictive` (feature/prediction-time leakage) | 8/8 | **8/8** | **8/8** |
| `data_model` (grain duplication) | 8/8 | 1/8 | **8/8** |
| `causal` (positivity) | 8/8 | 0/8 | 1/8 |
| `temporal` (immature cohort) | 8/8 | 0/8 | 0/8 |
| `statistical` (insufficient power) | 8/8 | 0/8 | 0/8 |
| `metric_semantics` (definition change) | 8/8 | 0/8 | 0/8 |
| `missingness` (informative missingness) | 8/8 | 0/8 | 0/8 |

**Both models retract perfectly on data leakage and almost never on the
five statistical/causal mechanisms.** Data leakage is arguably the most
heavily emphasized data-integrity failure in ML education and tooling —
it has a name every practitioner learns early. Positivity violations,
underpowered comparisons, metric-definition drift and informative
missingness are comparatively under-taught, harder to state in one
sentence, and easier for a model to soften into "the effect is probably
still there, just weaker" (`QUALIFY`) instead of withdrawing outright.

Codex's edge on `data_model` (8/8 vs Claude's 1/8) is the one place the two
models diverge in kind, not just degree — worth noting, not explained by
this data alone.

A one-sided exact binomial test (same method as the `emt-v1` write-up,
`p=1/3` null over the three non-`RETRACT` actions) on the pooled wrong
answers: `QUALIFY` accounts for 47/47 of Claude's errors (p = 3.76 × 10⁻²³)
and 39/39 of Codex's (p = 2.47 × 10⁻¹⁹). The directional bias itself is
statistically indisputable; what `emt-v2` adds is *which* mechanisms drive
it.

## Reading this honestly

- **n = 8 per class per model.** Enough to be confident the `predictive`
  vs. everything-else split is real (16/16 vs. 2/48 is not noise), not
  enough to trust the exact rate within a class to more than one
  significant figure.
- **Two models.** Whether this generalizes to other providers, or to
  Claude/Codex under a different prompt, is untested here.
- **One data-leakage framing.** The `predictive` scenarios all use the
  same "feature available after prediction time" mechanism. Whether the
  perfect score holds for other well-known leakage patterns (target
  leakage, train/test contamination) is a natural next benchmark
  extension, not something this run tested.
- **Not yet tested: agent + tool.** This run measures the LLM's *own*
  judgment with no access to Answerable. It says nothing about whether an
  agent given `assess_answerability` as a callable tool would defer to
  it and get these right — that is a different, not-yet-run experiment.

## Reproducing

```bash
python scripts/run_agent_harness.py \
  --cases benchmarks/releases/emt-v2/cases.jsonl \
  --agents claude,codex --repetitions 2 \
  --output runs/emt-v2-agents
python scripts/build_emt_results.py \
  --llm-decisions runs/emt-v2-agents/decisions.jsonl \
  --oracle benchmarks/releases/emt-v2/oracle.json \
  --output runs/emt-v2-results
```
