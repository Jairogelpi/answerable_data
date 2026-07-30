from __future__ import annotations

import unittest

from answerable.execution.errors import ExecutionTimedOut, UnsafePython
from answerable.execution.python_sandbox import PythonSandboxExecutor

FR_EXEC_002 = "FR-EXEC-002"
FR_EXEC_009 = "FR-EXEC-009"
FR_EXEC_010 = "FR-EXEC-010"


class PythonSandboxTests(unittest.TestCase):
    def test_phase_7_executes_a_bounded_pure_expression(self) -> None:
        executor = PythonSandboxExecutor("sum(data['values'])")
        self.assertEqual(executor.execute({"values": [1, 2, 3]}), 6)

    def test_phase_7_rejects_import_file_network_and_attribute_access(self) -> None:
        unsafe = (
            "__import__('socket')",
            "open('/tmp/x')",
            "data.__class__",
            "(lambda: 1)()",
        )
        for expression in unsafe:
            with self.subTest(expression=expression), self.assertRaises(UnsafePython):
                PythonSandboxExecutor(expression)

    def test_phase_7_rejects_unknown_names_and_statements(self) -> None:
        with self.assertRaises(UnsafePython):
            PythonSandboxExecutor("secret")
        with self.assertRaises(UnsafePython):
            PythonSandboxExecutor("x = 1")
        with self.assertRaises(ValueError):
            PythonSandboxExecutor("1", timeout_seconds=0)

    def test_phase_7_discards_timed_out_work(self) -> None:
        executor = PythonSandboxExecutor("2 ** 999999999", timeout_seconds=0.01)
        with self.assertRaises(ExecutionTimedOut):
            executor.execute({})

    def test_phase_7_reports_expression_runtime_failure_without_details(self) -> None:
        executor = PythonSandboxExecutor("data['missing']")
        with self.assertRaisesRegex(UnsafePython, "expression failed"):
            executor.execute({})


if __name__ == "__main__":
    unittest.main()
