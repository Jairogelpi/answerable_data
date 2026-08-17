# Roadmap

Answerable v0.1.0 is the validity-engine technical preview. The roadmap prioritizes a usable vertical slice rather than adding more architecture.

## v0.2 — First complete workflow

- [x] One command: CSV/Parquet + question → Evidence Warrant.
- [x] Real CLI arguments, exit codes and JSON output.
- [x] Golden campaign-retention case with deterministic expected artifacts.
- [x] Reproducible Markdown and JSON warrant export.
- [x] Documentation tested from a clean environment.
- [x] AnswerableBench cases executed through the runner rather than scored from supplied observations.

## v0.3 — Evidence benchmark

- [x] Epistemic Mutation Testing with `KEEP`, `QUALIFY`, `RETRACT` and `REVERSE` oracles.
- [x] Four mutation families over 12 scenarios: 48 paired runner executions.
- [x] Release gate for action accuracy, unsafe-KEEP rate and per-family accuracy.
- [x] Semantic reproducibility hash independent of output path.
- [x] External-agent evaluator requiring 3 agents × 2 repetitions × 48 pairs.
- [x] Paired agent metrics: oracle accuracy, unsafe-KEEP rate and repeat consistency.
- [x] Mutation benchmark executed from the installed wheel in CI.

## v0.4 — Analyst workflow

- Guided question framing and field mapping.
- Inspectable evidence graph and claim inspector.
- Notebook export.
- Benchmark expansion for joins, broader cohorts, leakage and missingness.
- Published external LLM comparison runs using the locked EMT protocol.

## Later

- Stable REST and MCP transport implementations.
- Additional warehouse adapters after connector-conformance proof.
- Optional LLM framing limited to structured interpretation.
- Hosted product only after the open-source workflow is reliable.

Non-goal: increasing feature count at the expense of deterministic evidence and claim safety.
