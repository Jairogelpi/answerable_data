# Answerable SDD — Delivery Phases 13–15

## Phase 13 — Evidence graph and deterministic verdicts

The evidence graph accepts only typed nodes and edges, rejects missing endpoints, duplicates, and
cycles, and requires every emitted claim or recommendation to reach source evidence. Stable exports
sort all content and include a content hash. Contradictory edges remain in the complete export, while
the reduced view always preserves blocker paths.

The verdict engine implements the normative precedence without an LLM. Every blocker has explicit
repairability. Allowed and forbidden claims are generated separately after linting causal language,
population, period, unsupported absence claims, relative changes without baselines, unreliable
subgroups, and recommendations without a decision. Repair planning selects the smallest sufficient
recoverable item.

## Phase 14 — Warrant and permitted analysis

Warrants contain exactly the seventeen canonical sections. Canonical JSON is copied at issuance,
sorted, hashed, and held immutably. JSON, Markdown, and HTML derive from that same canonical content.
Optional HMAC-SHA256 signing binds signer intent to the content hash; previous unsigned or signed
warrants remain independently verifiable after a superseding warrant is issued.

Analysis Plans are separate immutable objects. They require question, estimand, validated data,
method, transformations, diagnostics, uncertainty, sensitivity, visualization, reporting language,
acceptance criteria, and an optional executable reference. Execution must append new evidence rather
than rewriting the warrant or its assessment history.

## Phase 15 — API, Python, CLI, and MCP

The provider-neutral API service demonstrates `/v1` semantics: JSON bodies, required idempotency
keys, replay-safe creates, optimistic ETag concurrency, and RFC 9457-style problem details. The
public Python package exposes typed Assessment, AssessmentPolicy, QuestionContract, Verdict, assess,
and verify_warrant symbols.

The CLI exposes the normative command families and deterministic JSON output with exit codes. MCP
exposes the eight specified tool names, always returns structured content, strips raw rows and
secrets by default, and requires explicit raw-row scope. All adapters call deterministic core
objects; none can override the verdict or mutate issued warrants.

## TDD evidence

Tests cover orphan claims, cycles, contradictions, reduced blocker paths, every verdict precedence
branch, claim-policy violations, minimal repair selection, canonical immutability, signing and old
warrant verification, supersession, analysis-plan completeness, API idempotency/ETags/problem
details, CLI JSON/exit codes, and MCP disclosure enforcement.
