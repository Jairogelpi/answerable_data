# Recorded evaluation — 2026-09-14

Both engine versions ran the same 12 cases and evaluator in this environment.
The baseline is repository commit `59749d9060c43f0b833a85de1cc3cc3f7e39ddc9`.
The corrected source is identified by `engine_sha256` in `after.json` and the
commit containing this report. `cases_sha256` is identical in both reports.

| Metric | Before | Corrected |
| --- | ---: | ---: |
| Valid exact descriptive claims | 4 | 4 |
| Invalid claims | 8 | 8 |
| Invalid claims in `allowed_claims` | 8 / 8 | 0 / 8 |
| Valid claims omitted from `allowed_claims` | 0 / 4 | 0 / 4 |
| Valid claims denied by the primary release gate | 2 / 4 | 0 / 4 |
| Execution errors | 0 | 0 |

The baseline's contradictory verdict/claim outputs are why both claim-level and
release-level metrics are reported. The 8/8 count does not mean every downstream
consumer would publish those claims: a consumer obeying the primary verdict
might reject them despite their appearance in `allowed_claims`.

This is a small, deliberately targeted regression suite. Datasets come from
outside Answerable; questions and admissibility labels were authored for this
review. Four duplicate cases are artificial perturbations. There is no claim
that these observations estimate general accuracy or were independently judged.

## Real agent comparison

**Not run.** The environment had neither Claude/Codex CLI on PATH nor
OpenAI/Anthropic/Gemini API keys. `agent-preflight.json` records zero decisions,
null metrics and the missing adapter. Its manifest describes 48 planned decisions
(12 cases × 2 repetitions × 2 arms); planned decisions are not observations.

No agent/tool efficacy result is claimed. See the parent suite README for the
command and adapter contract needed to run the paired experiment with a pinned,
authenticated real model. Test doubles only exercise harness plumbing in tests.

## Reproduce the before/after comparison

From the corrected checkout, with dependencies installed:

```bash
python scripts/evaluate_external.py --output runs/external-after-reproduced
git worktree add --detach ../answerable-before 59749d9060c43f0b833a85de1cc3cc3f7e39ddc9
PYTHONPATH=../answerable-before/src python scripts/evaluate_external.py --output runs/external-before-reproduced
```

The baseline command intentionally exits 1 because unsafe allowed claims were
found. The corrected command exits 0. Numerical observed means are also compared
with independently computed means in the automated tests.
