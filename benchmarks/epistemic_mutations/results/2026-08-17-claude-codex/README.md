# AnswerableBench EMT — run 2026-08-17 (Claude, Codex)

Real agent decisions against the frozen `emt-v1` case set
([`benchmarks/releases/emt-v1/`](../../../releases/emt-v1/)), produced by
[`scripts/run_agent_harness.py`](../../../../scripts/run_agent_harness.py)
and scored by
[`scripts/build_emt_results.py`](../../../../scripts/build_emt_results.py).

## What ran

| Agent | Model | Decisions | Protocol |
| --- | --- | --- | --- |
| Claude | `claude-sonnet-5` (resolved from the CLI's own response) | 96/96 | 48 cases × 2 repetitions |
| Codex | `gpt-5.6-sol` | 96/96 | 48 cases × 2 repetitions |
| Answerable | deterministic engine, not an LLM | 96/96 | run twice for protocol parity; identical both times by construction |

`raw.jsonl` has one record per call: full prompt, raw response, resolved
model, timestamp, latency, token usage, cost where the CLI reports it, and
the case hash. `decisions.jsonl` is the schema
`scripts/score_mutation_agents.py` and `evaluate_agent_matrix` read.

## What did not run

**Gemini is not in this result.** The first attempt (`gemini-2.5-flash`)
hit a 20-requests/**day** free-tier cap 20 calls in; a second attempt on
`gemini-2.5-flash-lite` with proper throttling still lost most calls to
persistent 429s. 20 partial decisions exist in
`../../../../runs/` locally (gitignored, not committed) but are too
incomplete to report with the same confidence as Claude and Codex, so they
are excluded here rather than presented as a weaker fourth column.
Re-running Gemini to completion is future work, not a claim made by this
result.

## Results

```
agent       accuracy  unsafe  overreact  consist
answerable    100.0%    0.0%       0.0%   100.0%
codex          83.3%    0.0%       0.0%   100.0%
claude         77.1%    0.0%       0.0%    95.8%
```

- **Unsafe KEEP** (kept a conclusion that should have been retracted or
  reversed) is **0% for every agent tested.** Neither model's failure mode
  is "ignores broken evidence."
- **Overreaction** (changed a conclusion that should have stayed) is also
  0% for every agent.

### Where they actually fail: RETRACT on evidence invalidation

The 12 `evidence_invalidation` scenarios (× 2 repetitions = 24 cases each)
destroy a validity condition — positivity, a completed observation window,
or one-row-per-entity grain — and the correct action is `RETRACT`, not a
softer `QUALIFY`.

| Agent | RETRACT correct | Dominant wrong answer | P(that concentration by chance)\* |
| --- | --- | --- | --- |
| Answerable | 24/24 | — | — |
| Codex | 8/24 | `QUALIFY`, 16/16 of its errors | 2.32 × 10⁻⁸ |
| Claude | 2/24 | `QUALIFY`, 22/22 of its errors | 3.19 × 10⁻¹¹ |

\* One-sided exact binomial test (`math.comb`, no external dependency): the
null hypothesis is that a wrong answer is drawn uniformly among the three
non-`RETRACT` actions (`p = 1/3`) — i.e. "wrong, but not systematically
wrong in one direction." The p-value is the probability of seeing at least
that many `QUALIFY` errors, out of that many total errors, under that null.
Both models clear conventional significance thresholds by many orders of
magnitude: when these two models are wrong on evidence invalidation, they
are not randomly wrong — they systematically **soften** the conclusion
instead of retracting it.

## Reading this honestly

- **n = 24 per model**, from **12 independent scenarios** across 3 failure
  classes (4 scenarios each), not 100+. The direction of the effect is
  statistically decisive; the precision of the *rate* (2/24, 8/24) is not —
  a wider case set (more scenarios per failure class) would narrow the
  confidence interval on the rate itself, not the finding that the
  direction is non-random.
- **Two models, not three.** Codex and Claude fail the same way; whether
  that generalizes to Gemini or other providers is untested here.
- **One prompt style.** Both models saw the same evidence-summary JSON and
  the same judge system prompt
  (`scripts/run_agent_harness.py:_JUDGE_SYSTEM_PROMPT`). A different prompt
  design could change the absolute accuracy numbers; it is less obviously
  able to change *which* wrong answer models converge on, since that
  pattern held across two different providers under the same prompt.
- Answerable's 100% here is not a separate claim from its release-gate
  score — it is the same deterministic engine, run through the same
  scoring pipeline as the other two agents for a fair, apples-to-apples
  comparison, not a number quoted from a different context.

## Reproducing

```bash
export GEMINI_API_KEY=...   # optional; omit to run only claude,codex
python scripts/run_agent_harness.py --agents claude,codex --repetitions 2 \
  --output runs/emt-agents
python scripts/build_emt_results.py --llm-decisions runs/emt-agents/decisions.jsonl \
  --output runs/emt-results
```
