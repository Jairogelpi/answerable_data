# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [Unreleased]

### Added
- `AssessmentRunner`: one orchestrator wiring ingestion, checks, evidence graph, verdict, repair plan and warrant.
- `answerable assess --data --question --output --format`, with exit code `2` for a blocked verdict.
- `answerable warrant verify --warrant`, with exit code `3` for a tampered warrant.
- Positivity/overlap check: a covariate stratum must contain both treatment levels.
- Question files in YAML or JSON, declaring the contract, column roles, causal contract and candidate claims.
- Plain-language `warrant.md` export alongside the canonical JSON artifacts.
- Golden `examples/campaign_retention` case, executed in CI and covered by an end-to-end test.

### Planned
- Execute AnswerableBench cases through the runner instead of scoring supplied observations.
- Publish installable package artifacts after release-candidate validation.

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
