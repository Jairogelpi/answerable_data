"""Real, runnable MCP server: `answerable mcp` — stdio transport.

Wraps `mcp_handlers.HANDLERS` (real implementations, not fakes) behind
`MCPServer`'s disclosure-scoping dispatcher, and exposes each tool with a
typed signature so the client (Claude Code, Codex, any MCP host) gets a
real JSON schema per tool instead of one opaque args blob.

This is the "epistemic firewall" made connectable: an agent adds this
server once, then calls `assess_answerability` before asserting a causal
claim, the same way the README's CLAUDE.md/AGENTS.md snippet does through
a shell command -- just without the shell.
"""

from __future__ import annotations

from typing import cast

from answerable.interfaces.mcp import MCPDisclosure, MCPServer
from answerable.interfaces.mcp_handlers import HANDLERS

_server = MCPServer(HANDLERS)


def _call(name: str, args: dict[str, object]) -> dict[str, object]:
    result = _server.call(name, args, disclosure=MCPDisclosure.METADATA_ONLY)
    return cast(dict[str, object], result["structuredContent"])


def build_server() -> object:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(
        "answerable",
        instructions=(
            "Test whether evidence actually supports an analytical conclusion before "
            "asserting it. Call assess_answerability before making any causal claim "
            "('X caused Y', 'X led to Y'); if the verdict is not ANSWERABLE or "
            "ANSWERABLE_WITH_ASSUMPTIONS, do not make the causal claim -- state the "
            "blocker instead and offer only the supported (usually descriptive) claim."
        ),
    )

    @mcp.tool()
    def frame_question(data: str, output: str | None = None) -> dict[str, object]:
        """Scaffold a question.yaml by inspecting a data file's columns.

        Guesses entity/event-time/treatment/outcome/covariate roles from the
        file's own schema. Fields only a human can decide (the question text,
        the claims, the causal design) come back as explicit TODOs, not
        guesses -- fill those in (or ask the user) before assess_answerability.
        """
        return _call("frame_question", {"data": data, "output": output})

    @mcp.tool()
    def inspect_data(data: str) -> dict[str, object]:
        """Profile a data file's columns: names, types, null/distinct counts.

        Never returns row-level data.
        """
        return _call("inspect_data", {"data": data})

    @mcp.tool()
    def assess_answerability(data: list[str], question: str, output: str) -> dict[str, object]:
        """Run the real validity engine: ingestion, checks, verdict, Evidence Warrant.

        `question` is a question.yaml/json path (see frame_question). Returns
        the verdict, blockers, and which claims are and are not supported.
        A verdict other than ANSWERABLE/ANSWERABLE_WITH_ASSUMPTIONS means the
        requested causal claim is blocked -- do not make it.
        """
        return _call("assess_answerability", {"data": data, "question": question, "output": output})

    @mcp.tool()
    def get_assessment(output: str) -> dict[str, object]:
        """Re-read the verdict and warrant from a previous assess_answerability run."""
        return _call("get_assessment", {"output": output})

    @mcp.tool()
    def explain_finding(output: str, finding_id: str) -> dict[str, object]:
        """Look up one finding (e.g. positivity_violation) from a previous run by its code."""
        return _call("explain_finding", {"output": output, "finding_id": finding_id})

    @mcp.tool()
    def design_missing_evidence_plan(output: str) -> dict[str, object]:
        """Return the repair plan: what evidence would remove this run's blockers."""
        return _call("design_missing_evidence_plan", {"output": output})

    @mcp.tool()
    def generate_analysis_plan(output: str) -> dict[str, object]:
        """Return the check plan that was executed for a previous run."""
        return _call("generate_analysis_plan", {"output": output})

    @mcp.tool()
    def verify_warrant(warrant: str) -> dict[str, object]:
        """Verify a warrant's signature hasn't been tampered with since issuance."""
        return _call("verify_warrant", {"warrant": warrant})

    return mcp


def run_stdio() -> None:
    build_server().run()  # type: ignore[attr-defined]


__all__ = ["build_server", "run_stdio"]
