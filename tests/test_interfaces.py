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
        self.assertEqual(code, 2)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["action"], "verify")
        self.assertEqual(payload["code"], "warrant_required")
        self.assertNotIn("valid", payload)

    def test_unimplemented_commands_fail_loudly(self) -> None:
        for command in ("frame", "plan", "execute", "inspect"):
            output = StringIO()
            with redirect_stdout(output):
                code = main(("--json", command))
            self.assertNotEqual(code, 0, f"{command} silently reported success")
            payload: dict[str, object] = json.loads(output.getvalue())
            self.assertEqual(payload.get("status"), "error")
        for action in ("add", "test"):
            output = StringIO()
            with redirect_stdout(output):
                code = main(("--json", "source", action))
            self.assertNotEqual(code, 0, f"source {action} silently reported success")

    def test_warrant_show_and_export_round_trip(self) -> None:
        import tempfile
        from pathlib import Path

        from answerable.demo import run_demo

        with tempfile.TemporaryDirectory() as tmp:
            _, run = run_demo("causal", Path(tmp) / "demo")
            warrant_path = run.artifacts["warrant"]

            output = StringIO()
            with redirect_stdout(output):
                code = main(("--json", "warrant", "show", "--warrant", str(warrant_path)))
            self.assertEqual(code, 0)
            payload: dict[str, object] = json.loads(output.getvalue())
            self.assertIn("warrant_id", payload)
            self.assertIn("data", payload)

            output = StringIO()
            with redirect_stdout(output):
                code = main(
                    (
                        "--json",
                        "warrant",
                        "export",
                        "--warrant",
                        str(warrant_path),
                        "--format",
                        "markdown",
                    )
                )
            self.assertEqual(code, 0)
            export_payload: dict[str, object] = json.loads(output.getvalue())
            rendered: str = str(export_payload["rendered"])
            self.assertIn("## ", rendered)

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
