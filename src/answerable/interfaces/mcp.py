from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum


class MCPDisclosure(StrEnum):
    NONE = "none"
    METADATA_ONLY = "metadata_only"
    SAMPLE_REDACTED = "sample_redacted"
    RAW_ROWS = "raw_rows"


class MCPServer:
    TOOLS = frozenset(
        {
            "frame_question",
            "inspect_data",
            "assess_answerability",
            "get_assessment",
            "explain_finding",
            "design_missing_evidence_plan",
            "generate_analysis_plan",
            "verify_warrant",
        }
    )

    def __init__(
        self, handlers: dict[str, Callable[[dict[str, object]], dict[str, object]]]
    ) -> None:
        if not set(handlers) <= self.TOOLS:
            raise ValueError("unknown MCP tool")
        self._handlers = handlers

    def call(
        self,
        name: str,
        arguments: dict[str, object],
        *,
        disclosure: MCPDisclosure = MCPDisclosure.METADATA_ONLY,
        raw_rows_scoped: bool = False,
    ) -> dict[str, object]:
        if name not in self._handlers:
            raise KeyError(name)
        if disclosure is MCPDisclosure.RAW_ROWS and not raw_rows_scoped:
            raise PermissionError("raw rows require explicit scope")
        result = self._handlers[name](arguments)
        if not raw_rows_scoped:
            result = {
                key: value
                for key, value in result.items()
                if key not in {"rows", "raw_rows", "secrets"}
            }
        return {"tool": name, "structuredContent": result, "disclosure": disclosure.value}
