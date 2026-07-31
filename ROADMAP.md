# Roadmap

Answerable v0.1.0 is the validity-engine technical preview. The roadmap prioritizes a usable vertical slice rather than adding more architecture.

## v0.2 — First complete workflow

- One command: CSV/Parquet + question → Evidence Warrant.
- Real CLI arguments, exit codes and JSON output.
- Golden campaign-retention case with deterministic expected artifacts.
- Reproducible Markdown and JSON warrant export.
- Documentation tested from a clean environment.

## v0.3 — Analyst workflow

- Guided question framing and field mapping.
- Inspectable evidence graph and claim inspector.
- Notebook export.
- Benchmark expansion for joins, cohorts, leakage and missingness.

## Later

- Stable REST and MCP transport implementations.
- Additional warehouse adapters after connector-conformance proof.
- Optional LLM framing limited to structured interpretation.
- Hosted product only after the open-source workflow is reliable.

Non-goal: increasing feature count at the expense of deterministic evidence and claim safety.
