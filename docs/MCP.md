# Answerable MCP integration

Answerable ships a real MCP server in the Python package. It runs over stdio, exposes typed tool schemas, and routes every assessment through the same deterministic engine used by the CLI.

## Install

```bash
python -m pip install "answerable-data[mcp]"
answerable doctor
```

The MCP extra installs the official Python MCP SDK dependency used by `answerable mcp`.

## Claude Code

```bash
claude mcp add answerable -- answerable mcp
```

## Codex

```bash
codex mcp add answerable -- answerable mcp
```

## Generic MCP host

Configure a stdio server with:

```json
{
  "command": "answerable",
  "args": ["mcp"]
}
```

If the host runs outside the environment where Answerable is installed, point `command` to the full path of the `answerable` executable in that environment.

## Tools

| Tool | Purpose |
| --- | --- |
| `frame_question` | Inspect a dataset and scaffold a question contract with unresolved analytical choices left explicit. |
| `inspect_data` | Return column-level metadata, counts, types and a fingerprint without exposing row-level data. |
| `assess_answerability` | Execute ingestion, validity checks, verdict construction and Evidence Warrant generation. |
| `get_assessment` | Reload the verdict and warrant from a completed assessment. |
| `explain_finding` | Retrieve the evidence behind a specific finding or blocker. |
| `design_missing_evidence_plan` | Return the repair plan for evidence that is currently insufficient. |
| `generate_analysis_plan` | Return the deterministic check plan used by an assessment. |
| `verify_warrant` | Verify that an Evidence Warrant has not been modified after issuance. |

## Recommended agent policy

The MCP server is most useful when the agent treats the verdict as a hard epistemic boundary rather than optional advice.

```text
Before asserting a causal, predictive, diagnostic or prescriptive claim:
1. Frame the question if no question contract exists.
2. Call assess_answerability.
3. Read verdict, blockers, allowed_claims and forbidden_claims.
4. Never emit a forbidden claim.
5. If blocked, state the blocker and use only an allowed narrower claim.
6. Preserve the Evidence Warrant with the analysis output.
```

For causal statements in particular, do not turn `PARTIALLY_ANSWERABLE`, `NOT_ANSWERABLE_YET`, `FUNDAMENTALLY_UNIDENTIFIABLE`, `INSUFFICIENT_POWER`, `DATA_INTEGRITY_FAILURE` or `ASSESSMENT_INCOMPLETE` into causal language.

## Example flow

```text
Agent wants to say
"Campaign exposure increased retention."
          │
          ▼
assess_answerability
          │
          ├── verdict: FUNDAMENTALLY_UNIDENTIFIABLE
          ├── blocker: positivity_violation
          ├── allowed: observed retention was higher in exposed users
          └── forbidden: campaign exposure caused higher retention
          │
          ▼
Agent retracts the causal statement and emits only the supported descriptive statement.
```

## Data disclosure boundary

`inspect_data` returns metadata only. The MCP dispatcher removes `rows`, `raw_rows` and `secrets` unless raw-row disclosure has been explicitly scoped by code. The packaged stdio server uses metadata-only disclosure.

This is a safety boundary, not a substitute for an independent security review. Do not expose production-sensitive datasets to an agent environment without reviewing the surrounding host, permissions and data-access model.

## Verify the installed MCP server

A local import smoke test should succeed:

```bash
python -c "from answerable.interfaces.mcp_stdio import build_server; build_server(); print('MCP OK')"
```

Then start the stdio server through the client configuration above. `answerable mcp` intentionally waits for an MCP host on stdin/stdout, so running it alone in a terminal appears to wait for input.

## Architecture

```text
Claude / Codex / MCP host
          │
          ▼
   answerable mcp
   FastMCP / stdio
          │
          ▼
 disclosure-scoped MCPServer
          │
          ▼
     real handlers
          │
          ▼
 AssessmentRunner / FileInspector / warrant verification
          │
          ▼
 deterministic artifacts + Evidence Warrant
```

The MCP layer does not call an LLM and does not implement a second assessment engine. It is an adapter over the same deterministic code paths exposed by the CLI.