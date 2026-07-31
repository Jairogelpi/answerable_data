# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [Unreleased]

### Planned
- Replace thin interface contracts with an end-to-end dataset-to-warrant workflow.
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
