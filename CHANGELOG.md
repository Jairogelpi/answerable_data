# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [Unreleased]

### Planned
- Execute AnswerableBench cases through the runner instead of scoring supplied observations.
- Expand epistemic mutation testing across joins, leakage, power, selection and metric drift.

## [0.2.0] - 2026-08-17

### Added
- `AssessmentRunner`: one orchestrator wiring ingestion, checks, evidence graph, verdict, repair plan and warrant.
- `answerable assess --data --question --output --format`, with exit code `2` for a blocked verdict.
- `answerable warrant verify --warrant`, with exit code `3` for a tampered warrant.
- `answerable demo` with causal-overlap, duplicate-grain and immature-cohort golden cases.
- Real `answerable doctor` runtime readiness checks.
- Positivity/overlap check: a covariate stratum must contain both treatment levels.
- Question files in YAML or JSON, declaring the contract, column roles, causal contract and candidate claims.
- Plain-language `warrant.md` export alongside the canonical JSON artifacts.
- Golden repository fixtures and deterministic demo tests.
- Product-first README and animated terminal demonstration.
- Tagged-release wheel smoke tests and PyPI Trusted Publishing workflow.

### Changed
- CLI human output now surfaces decisive blockers, supported claims, unsupported claims and artifact locations directly.
- Packaging metadata advances to `0.2.0` and positions Answerable as deterministic validity testing for analytics and AI conclusions.

## [0.1.0] - 2026-07-31

### Added
- Complete specification-driven analytical-validity domain.
- Deterministic evidence graph, verdict precedence, claim boundaries and repair plans.
- Immutable Evidence Warrants and verification.
- Guarded DuckDB/Python execution and concrete read-only data connectors.
- Data-quality, temporal, experimental, causal, predictive, diagnostic and prescriptive checks.
- Python, CLI, API, MCP and accessible HTML contract surfaces.
- Enterprise governance primitives and AnswerableBench release gate.
- 114 traced requirements, 137 tests plus 22 subtests, and a 95% coverage gate.
- CI, CodeQL, package clean-install verification and provenance-attested GitHub releases.

### Security
- SQL parsing rejects mutations and multi-statement execution.
- Bounded query results, secret redaction and fail-closed verdict behavior.
