from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from answerable.cli import main
from answerable.interfaces import ApiService, MCPDisclosure, MCPServer

FR_API_001 = "FR-API-001"
FR_API_002 = "FR-API-002"
FR_CLI_001 = "FR-CLI-001"
FR_MCP_001 = "FR-MCP-001"
FR_MCP_002 = "FR-MCP-002"


class InterfaceTests(unittest.TestCase):
    def test_phase_15_api_idempotency_problem_details_and_etags(self) -> None:
        api = ApiService()
        first = api.create("a1", {"question": "q"}, idempotency_key="k")
        self.assertEqual(first, api.create("a1", {"question": "q"}, idempotency_key="k"))
        conflict = api.create("a2", {"question": "other"}, idempotency_key="k")
        self.assertEqual(conflict.status, 409)
        self.assertEqual(conflict.body["code"], "concurrency_conflict")
        updated = api.patch("a1", {"question": "new"}, if_match='"1"')
        self.assertEqual(updated.etag, '"2"')
        self.assertEqual(api.patch("a1", {}, if_match='"1"').status, 409)

    def test_phase_15_cli_json_and_exit_code_contract(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(("--json", "warrant", "verify"))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["action"], "verify")

    def test_phase_15_mcp_returns_structured_redacted_content(self) -> None:
        server = MCPServer(
            {"inspect_data": lambda _: {"columns": ["id"], "rows": [[1]], "secrets": "x"}}
        )
        result = server.call("inspect_data", {}, disclosure=MCPDisclosure.METADATA_ONLY)
        self.assertEqual(result["structuredContent"], {"columns": ["id"]})
        with self.assertRaises(PermissionError):
            server.call("inspect_data", {}, disclosure=MCPDisclosure.RAW_ROWS)
        scoped = server.call(
            "inspect_data", {}, disclosure=MCPDisclosure.RAW_ROWS, raw_rows_scoped=True
        )
        self.assertIn("rows", scoped["structuredContent"])


if __name__ == "__main__":
    unittest.main()
