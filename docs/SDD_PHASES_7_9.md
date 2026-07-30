# Answerable SDD — Delivery Phases 7–9

## Status and scope

This document is the executable design for phases 7–9 of `docs/PRODUCT_SPEC.md`. It extends the
previous SDDs. Public behavior is traced in `requirements/traceability.yaml`, validated by schemas,
and proved by tests written before implementation.

## Phase 7 — Reproducible execution

### Contracts

`ExecutionRequest` identifies an executor, JSON-compatible payload, idempotency key, and bounded
attempt count. Its fingerprint is SHA-256 over canonical JSON. Reusing an idempotency key:

- returns the immutable original artifact when the request fingerprint is identical;
- fails with `IdempotencyConflict` when any execution input differs.

Successful artifacts are content-addressed over the engine version, executor, request fingerprint,
attempt count, and result. Timestamps are deliberately excluded from identity.

`ExecutionEngine` has an explicit executor registry. Only `RetryableExecutionError` is retried.
Cancellation is checked before every attempt and before persistence; cancelled or failed work never
becomes a successful artifact.

### Python security boundary

`PythonSandboxExecutor` accepts an expression, not a program. AST validation permits literals,
collections, arithmetic, comparisons, subscripting of JSON input, and seven pure built-ins. It
rejects imports, assignments, lambdas, comprehensions, attribute access, unknown names, and arbitrary
calls. The expression runs in isolated Python mode with no site packages, a reduced built-in set,
captured output, and a hard wall-clock timeout. Arbitrary third-party code is outside this boundary.

## Phase 8 — Structured question framing

The model-provider boundary is the small `StructuredModel` protocol. Provider output must match the
closed proposal contract exactly:

- normalized question;
- descriptive, diagnostic, predictive, causal, or unknown analysis type;
- inferred fields with value, provenance, and confidence;
- ambiguities and clarification questions.

Unknown keys — including `verdict` and `tool_calls` — are rejected. Column-derived inferences must
refer to a known column. Invalid output receives one repair attempt and then fails closed.

Question and context are marked as untrusted data. They can influence the proposal but cannot change
policy, invoke execution, or issue an answer. `NoLLMFramer` provides deterministic offline behavior
and surfaces missing material definitions rather than inventing them.

## Phase 9 — Contextual data and temporal quality

`DataQualityAssessor` detects schema drift, required-field missingness, duplicate declared keys,
referential-integrity failures, inconsistent units, and truncation. Severity is question-relative:
failure of a required analytical field blocks; the same defect in an irrelevant field warns.

Missingness is measured globally and by observed group. MCAR, MAR, and MNAR are reported only as
hypotheses; this layer never claims an untestable mechanism as fact.

`TemporalAssessor` checks typed and timezone-aware event time, prediction-time feature leakage,
cohort maturity, right censoring/delayed labels, and metric-definition changes. These findings block
when temporal ordering or observation windows cannot support the requested analysis.

## Failure semantics

All failures are typed and fail closed. No timeout, cancellation, invalid model output, truncated
input, leakage, immature cohort, or changed metric definition may silently produce an `answerable`
outcome.

## TDD evidence

Phase tests cover normal paths, invalid contracts, malicious framing output, idempotency conflicts,
retry exhaustion, cancellation, sandbox escape classes, contextual severity, missingness
hypotheses, temporal leakage, censoring, and definition changes. CI enforces Ruff, strict mypy,
schema validation, traceability, Python 3.11/3.12 tests with at least 95% coverage, package build,
and CodeQL.
