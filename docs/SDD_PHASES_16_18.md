# Answerable SDD — Delivery Phases 16–18

## Phase 16 — Web product

The server-rendered result contract places verdict and executive explanation before advanced
provenance. Allowed claims, forbidden claims, blockers, and assumptions use distinct labelled
sections. A skip link, semantic headings, text status, keyboard focus target, and labelled evidence
tree establish the accessibility baseline. All fifteen normative screens have stable route keys.

## Phase 17 — Enterprise connectors and governance

Connectors implement one read-only conformance protocol covering health, catalog, bounded query,
capabilities, and mutation rejection. Tenant context is mandatory for governed storage, secrets,
audit, retention, backup, and restore. RBAC fails closed. Secrets and email identifiers are redacted
before telemetry; the append-only audit chain is hashed and tenant reads are isolated.

Backups contain one tenant only and restore through validation into the same isolation boundary.
Private deployments can use these contracts without changing the analytical domain.

## Phase 18 — Benchmark and release hardening

AnswerableBench requires the fifteen normative families and aligns every case with exactly one
observation. Release results report verdict accuracy, blocker recall, and causal-safety violations.
A release passes only at perfect expected-case accuracy/recall with zero causal-safety violations.

The threat model, disaster-recovery procedure, migration/rollback rehearsal, and release checklist
are versioned alongside code. CI runs the benchmark smoke suite, package build, dependency audit,
and existing CodeQL workflow. Thresholds remain unchanged.
