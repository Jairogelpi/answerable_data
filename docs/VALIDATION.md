# Validation evidence

Status: alpha. Evidence reviewed on 2026-09-16. This document separates software
verification from evidence of analytical validity and integration benefit.
The complete target in PRODUCT_SPEC.md is not a statement that all workflows
are implemented or independently validated.

## Recorded evidence

The following results concern commit `c8fe2dae8053248dd519c1dd5549ad3e5d72174e`
(PR #22), before the release-readiness changes. They are not new results for every
future commit. The additional version regression test must pass on the next revision.

| Check | Observed result | Scope |
| --- | --- | --- |
| Local complete verification | 215 tests, 96.01% branch-aware coverage; Ruff and strict mypy passed | Software regression checks |
| Schemas and traceability | 21 schemas and 119 requirement entries passed | Structure and traceability, not scientific validation |
| Post-merge CI | Linux Python 3.11/3.12 and clean wheel passed | [CI run](https://github.com/Jairogelpi/answerable_data/actions/runs/34944933551) |
| CodeQL | Passed | [Run](https://github.com/Jairogelpi/answerable_data/actions/runs/34944933538); no claim of comprehensive security certification |
| Local CLI and MCP | Three demos, actual stdio initialize/list/assessment call, valid warrant accepted and altered warrant rejected | Local Linux manual checks; not real-agent efficacy |
| EMT | 112 mutation pairs passed | Project-authored scenarios/oracles, correlated cases |
| External data | Four valid claims retained; eight invalid claims blocked; zero execution errors | Two external datasets, 12 project-authored questions |
| Public version | Python reported 0.2.0 while package/CLI reported 0.3.0 | Release-readiness change corrects this inconsistency |

External before/after reports, hashes and limitations are preserved in
[the recorded evaluation](../benchmarks/external/results/2026-09-14/README.md).
In that comparison, invalid entries in `allowed_claims` fell from 8/8 to 0/8,
and valid claims denied by the primary gate fell from 2/4 to 0/4.
These small, targeted counts do not estimate general error rates.

Historical Claude/Codex EMT runs compare agents without Answerable against the
engine on frozen project oracles. They do not measure the effect of giving an
agent the tool. The new paired harness records **not_run**, zero actual decisions
and null metrics until an authenticated real-model adapter is provided.

## Windows portability follow-up

After PR #23 merged as `c432104cdcfdfcfd51655a232646d3e95db2999b`,
[CI](https://github.com/Jairogelpi/answerable_data/actions/runs/34963430790)
passed all three package jobs and both Linux quality jobs. Windows quality ended
with 213 passed and three failed tests: source hash mismatch in the external suite.
A successful package installation did not establish a passing Windows test suite.

A regression reproduces the mismatch with Git `core.autocrlf=true`. The follow-up
fix extends byte-preserving Git attributes to external snapshots and recorded
reports. Strict SHA-256 checking is retained. Its CI must pass on Windows before
the portability defect is considered resolved; the old failing run remains evidence.

## Current boundaries

- The runner currently assesses the first data source. Multi-source contracts or
  connector primitives do not establish general multi-table assessment support.
- Causal support is conditional on explicit assumptions; absence of unmeasured
  confounding cannot be verified from empirical overlap.
- Full discrete-stratum overlap is conservative for continuous covariates.
- Observed group means are descriptive; adjusted causal effect estimation and
  general verification of arbitrary prose/numbers are not implemented.
- Warrant verification checks integrity. It is not a scientific truth guarantee.
- CLI, Python and stdio MCP are executable interfaces. HTTP/web contract modules
  do not constitute a complete hosted product.

## Reproduce software and smoke evaluation

Use a clean Python 3.11 or 3.12 environment from the checkout:

```bash
python -m pip install -e ".[dev]"
python -m ruff format --check .
python -m ruff check .
python -m mypy
python -m pytest
python scripts/validate_schemas.py
python scripts/check_traceability.py
python scripts/evaluate_external.py --output runs/external-validation
python -m build
python scripts/check_distribution.py
```

On Windows, avoid global Python/plugin contamination by calling the environment
interpreter explicitly (activation is optional):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

An interrupted pytest run is incomplete. A version-specific CI pass is not
proof of compatibility with untested Python versions or operating systems.
The clean-distribution script installs the built wheel into an isolated temporary
venv and tests public version, CLI, MCP construction and the mutation benchmark
outside the source checkout. It requires access to package dependencies.

## Missing evidence

Independent questions and labels, dataset-level held-out evaluation, real-model
paired results, and external pilots remain pending. Windows jobs are introduced
in the release-readiness change; inspect that revision's CI before claiming a pass.
[Release criteria](RELEASE_CRITERIA.md) define the gates and their evidence owners.
