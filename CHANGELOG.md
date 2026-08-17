# Changelog

All notable changes follow Keep a Changelog and Semantic Versioning.

## [Unreleased]

## [0.3.0] - 2026-08-17

### Added
- Epistemic Mutation Testing (EMT) executed through the real `AssessmentRunner`.
- 28 deterministic scenarios across 7 failure classes crossed with four mutation families for 112 paired tests.
- `KEEP`, `QUALIFY`, `RETRACT` and `REVERSE` transition oracles.
- `answerable benchmark mutations` with a machine-readable `mutation_report.json`.
- Release gates for transition accuracy, unsafe-KEEP rate, per-family and per-failure-class accuracy.
- Output-path-independent semantic reproducibility hashes.
- External-agent evaluator enforcing 3 agents × 2 repetitions × 112 pairs (672 decisions).
- Paired external-agent metrics for oracle accuracy, unsafe-KEEP rate and repeat consistency.
- Clean-wheel CI execution of the mutation benchmark.
- Real engine detectors for the four new failure classes: `prediction_leakage` (feature/prediction timing), `insufficient_power` (statistical power on every assessment), `definition_change` (metric definition stability), `informative_missingness` (treatment-dependent outcome missingness).
- `answerable init --data <file> --output <question.yaml>` scaffolds a question file from a data file's own columns, to cut onboarding friction.
- `benchmarks/releases/emt-v2/` (7-class, 112-pair) frozen alongside the immutable `emt-v1` (3-class, 48-pair) archive.
- Real Claude/Codex EMT results published with a one-sided exact binomial significance test, and `docs/paper/paper.md` write-up.
- README sections on using Answerable as a tool call from Claude Code / Codex, and a full CLI command reference.
- Real MCP server (`answerable mcp`, `pip install 'answerable-data[mcp]'`): all 8 tools from `docs/PRODUCT_SPEC.md` §18.3 backed by real handlers (`AssessmentRunner`, `FileInspector`, `scaffold_question`, `verify_warrant`) via the existing disclosure-scoping `MCPServer`, connectable with `claude mcp add` / `codex mcp add`.
- Dedicated `docs/MCP.md` production integration guide for Claude Code, Codex and generic stdio MCP clients.
- MCP package and server smoke tests in pull-request CI and tagged-release validation.

### Changed
- AnswerableBench now executes evidence-changing benchmark cases through the runner instead of only scoring supplied observations.
- EMT oracle classification (`_derive_action`) now keys RETRACT on the specific blocker each scenario's failure class is designed to test, not "any blocker present" — needed once every assessment also runs the blanket statistical-power check.
- `_load()`'s outcome column uses `try_cast` instead of `cast`, so a missing/non-numeric outcome value is reported as a data-quality finding instead of crashing the run.
- README positioning now leads with deterministic claim validity, product differentiation, use cases and benchmark evidence before implementation detail.
- `answerable-data[mcp]` is now the primary documented adoption path for AI agents.
- PyPI project metadata now exposes MCP, research, benchmark, source, issue and changelog links.

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
