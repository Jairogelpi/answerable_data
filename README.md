<div align="center">

# Answerable

### Evidence before answers.

**Deterministic validity testing for analytics and AI conclusions.**

Your code has tests. Your data has tests. **Your conclusions should too.**

[![CI](https://github.com/Jairogelpi/answerable_data/actions/workflows/ci.yml/badge.svg)](https://github.com/Jairogelpi/answerable_data/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Jairogelpi/answerable_data/actions/workflows/codeql.yml/badge.svg)](https://github.com/Jairogelpi/answerable_data/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)

[60-second demo](#60-second-demo) · [Install](#install) · [Golden cases](#golden-cases) · [Evidence Warrants](#evidence-warrants) · [Architecture](#architecture)

</div>

> [!IMPORTANT]
> **Correct arithmetic does not guarantee a justified conclusion.** Answerable checks whether the available evidence supports the claim before allowing the claim to pass.

![Answerable terminal demo](docs/demo.svg)

## 60-second demo

Install the package, then run one command:

```bash
answerable demo
```

The default case contains a real observed retention difference, but exposed and unexposed customers have no comparable covariate overlap. A naive analysis can calculate the difference; Answerable refuses the causal attribution.

```text
Answerable demo
Case: Causal attribution trap
Question: Did campaign exposure increase 90-day retention?
Trap: The observed difference is real, but treatment has zero covariate overlap.

Verdict: FUNDAMENTALLY_UNIDENTIFIABLE
Blockers:
  x positivity_violation: No covariate stratum contains both exposed and unexposed entities.

Supported claims:
  + Exposed customers had higher observed 90-day retention than unexposed customers.

Unsupported claims:
  - The campaign caused higher 90-day retention.
```

That distinction is the product: **a number can be correct while the conclusion is wrong.**

## Install

### PyPI

The v0.2 release workflow publishes tagged distributions through PyPI Trusted Publishing:

```bash
python -m pip install answerable-data
answerable doctor
answerable demo
```

Until the first v0.2 tag is published, install the current source checkout:

```bash
git clone https://github.com/Jairogelpi/answerable_data.git
cd answerable_data
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
answerable doctor
answerable demo
```

`answerable doctor` verifies the runtime and core dependencies. A release is also tested by installing the built wheel into a clean virtual environment and running the demo from that wheel.

## Golden cases

Answerable ships three deliberately adversarial first-run cases:

| Demo | Broken assumption | Expected signal |
| --- | --- | --- |
| `answerable demo causal` | Treatment has zero covariate overlap | `positivity_violation` |
| `answerable demo grain` | One customer appears twice at a declared one-row-per-customer grain | `duplicate_entities` |
| `answerable demo maturity` | Recent cohorts have not completed the 90-day outcome window | `immature_cohort` |

The same cases are readable as normal repository fixtures under [`examples/`](examples/). They are not hand-authored verdicts: the engine executes checks against the data and question contract.

## Assess your own data

```bash
answerable assess \
  --data customers.csv \
  --question question.yaml \
  --output runs/my_assessment
```

An assessment executes this chain:

```text
question contract
      +
immutable data fingerprint
      ↓
deterministic checks
      ↓
evidence graph
      ↓
verdict
      ↓
repair plan
      ↓
Evidence Warrant
```

The run emits machine-readable artifacts plus a human-readable warrant, including `question_contract.json`, `data_inventory.json`, `check_plan.json`, `findings.json`, `evidence_graph.json`, `verdict.json`, `repair_plan.json`, `warrant.json` and `warrant.md`.

Exit codes are intentional: `0` means the requested conclusion is cleanly answerable, `2` means the analytical request is blocked, and `3` means warrant verification failed.

## Evidence Warrants

A warrant records what the data supports, what it does not support, the decisive evidence, assumptions, repair actions and provenance needed to reproduce the assessment.

Verify one:

```bash
answerable --json warrant verify --warrant runs/my_assessment/warrant.json
```

If the warrant is modified after issuance, verification fails.

## What Answerable is testing

Answerable is not a generic chat-with-data system and does not optimize for always returning an answer. It is a validity layer between evidence and conclusions.

Examples of failures it is designed to surface include:

- causal attribution without an identifiable comparison;
- incomplete outcome windows and right censoring;
- duplicated or ambiguous units of analysis;
- target or temporal leakage;
- unsafe joins and incompatible grain;
- underpowered or invalid experiments;
- unsupported causal, predictive, diagnostic or prescriptive language.

The core rule is:

> **The model may interpret. Tools measure. Rules verify. Evidence decides.**

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `ANSWERABLE` | Evidence supports the specified claim |
| `ANSWERABLE_WITH_ASSUMPTIONS` | Support depends on explicit assumptions |
| `PARTIALLY_ANSWERABLE` | A narrower claim is supportable |
| `NOT_ANSWERABLE_YET` | Repairable evidence is missing |
| `FUNDAMENTALLY_UNIDENTIFIABLE` | The requested effect cannot be identified |
| `INSUFFICIENT_POWER` | The design cannot detect a relevant effect |
| `DATA_INTEGRITY_FAILURE` | Data defects invalidate the result |
| `ASSESSMENT_INCOMPLETE` | Mandatory execution evidence is absent |

## Engineering evidence

The project is specification-driven and fail-closed. The verification suite enforces branch-aware coverage of at least 95%, strict mypy, Ruff, public-schema validation, requirement traceability, clean package build/install and CodeQL.

The current engine includes:

- content-hashed CSV, TSV, JSONL and Parquet intake;
- grain, join-cardinality and metric-semantic checks;
- temporal, missingness, experiment and statistical validity checks;
- causal, predictive, diagnostic and prescriptive contracts;
- guarded DuckDB and restricted Python execution;
- typed evidence graphs and deterministic verdict precedence;
- immutable, verifiable Evidence Warrants;
- SQLite, DuckDB and PostgreSQL-compatible read-only connectors;
- audit, retention and multi-tenant governance primitives;
- API, MCP and HTML contract surfaces.

## Architecture

```text
src/answerable/
├── application/   end-to-end assessment orchestration
├── framing/       question contracts
├── ingestion/     immutable file intake
├── analysis/      grain, joins and metrics
├── quality/       data and temporal validity
├── statistics/    experiments and inference
├── causal/        identification contracts
├── decision/      predictive/diagnostic/prescriptive rules
├── execution/     guarded DuckDB and Python
├── evidence/      graph, claims and verdicts
├── warrants/      canonical signed artifacts
├── enterprise/    connectors and governance
└── interfaces/    API and MCP contracts
```

`docs/PRODUCT_SPEC.md` is normative. `requirements/traceability.yaml` maps verified requirements to implementation and tests.

## Development

```bash
python -m pip install -e ".[dev]"
make verify
make build
```

A contribution is not complete until formatting, linting, strict typing, tests, coverage, schemas and traceability pass. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Current boundary

Answerable is still pre-1.0 software. The end-to-end assessment path, golden demos, validity core, warrants and verification path are executable. Some web/API/MCP surfaces remain contracts rather than a finished hosted product. Do not use production-sensitive datasets without an independent security and methodological review.

See [ROADMAP.md](ROADMAP.md), [SECURITY.md](SECURITY.md), [SUPPORT.md](SUPPORT.md) and [CITATION.cff](CITATION.cff).

---

<div align="center">

**Data can produce an answer. Answerable asks whether it can support the conclusion.**

</div>
