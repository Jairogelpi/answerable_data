# Answerable SDD — Delivery Phases 4–6

## Status

This document records the executable design for phases 4–6 of the normative product specification.
It extends, and does not replace, `docs/SDD_PHASES_1_3.md`.

## Phase 4 — File ingestion and DuckDB

### Supported sources

- CSV through `read_csv_auto` with full-file type inference.
- JSONL/NDJSON through newline-delimited `read_json_auto`.
- Parquet through `read_parquet`.

Every file is resolved to an absolute path, verified as a regular file, streamed through SHA-256,
and represented by an immutable `DataAssetSnapshot`.

### Profiling

Profiling records:

- content fingerprint and byte size;
- full row count;
- physical column types;
- null count per column;
- distinct count per column;
- whether the result came from full data or a sample.

The first implementation profiles full files. Pushdown, bounded approximate profiles, and warehouse
connectors remain later-phase work.

### Deterministic sampling

Rows are ordered by a DuckDB hash derived from all row values and the explicit seed. The result
records input fingerprint, seed, requested size, and an ordering fingerprint. Repeating an unchanged
input and seed produces the same sample under the pinned DuckDB dependency.

### Read-only execution

`DuckDBReadOnlyExecutor` accepts exactly one SQLGlot-parsed query expression. It rejects:

- DDL and DML;
- `COPY`;
- multiple statements;
- malformed SQL;
- external file and database scan functions.

Results are wrapped in an outer bounded query and expose whether rows were truncated.

## Phase 5 — Grain, joins, and metrics

### Grain

Single-column candidate keys are inferred only when a full profile reports zero nulls and distinct
count equal to row count. Results are `unique`, `ambiguous`, `no_key`, or `empty`. Composite-key
search is deliberately deferred until bounded combinatorial search is specified.

### Join impact

Join analysis measures:

- left and right row counts;
- duplicate keys on each side;
- one-to-one, one-to-many, many-to-one, or many-to-many cardinality;
- output row count;
- fan-out ratio.

Many-to-many joins fail closed with a blocker. One-to-many and many-to-one joins remain visible but
are not automatically blocked because validity depends on the intended target grain.

### Metrics

Metric definitions state type, grain, and expression. Ratio metrics require explicit numerator and
denominator. Reconciliation compares pre/post totals with a configured relative tolerance and
creates a blocker when conservation fails.

## Phase 6 — Skills and Check Plan

Skills are versioned planners. They may propose registered checks and clarification questions but
cannot issue verdicts.

The planner:

1. selects skills applicable to the analysis type;
2. adds policy-mandatory checks;
3. rejects unknown check types and duplicate IDs;
4. validates dependency existence;
5. topologically sorts the check DAG;
6. rejects cycles;
7. calculates total estimated cost;
8. reports maximum required disclosure;
9. returns deterministic check and clarification ordering.

## TDD proof

Tests were introduced before the four new packages existed. Collection initially failed for
`answerable.ingestion`, `answerable.execution`, `answerable.analysis`, and `answerable.planning`.
Implementation was then added until the focused suite passed.

## Security boundary

The read-only executor is not a general SQL sandbox. It is a restricted query adapter over
Answerable-controlled relations. Later database connectors must enforce source-side read-only
credentials, cost limits, and tenant policy in addition to AST validation.

