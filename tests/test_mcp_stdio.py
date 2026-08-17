from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("mcp", reason="mcp is an optional extra: pip install 'answerable-data[mcp]'")

from answerable.interfaces.mcp import MCPServer
from answerable.interfaces.mcp_stdio import build_server


def test_build_server_registers_every_contract_tool() -> None:
    server = build_server()

    tools = asyncio.run(server.list_tools())  # type: ignore[attr-defined]
    names = {tool.name for tool in tools}

    assert names == MCPServer.TOOLS
