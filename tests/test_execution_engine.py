from __future__ import annotations

import unittest

from answerable.execution.engine import (
    CancellationToken,
    ExecutionEngine,
    ExecutionRequest,
)
from answerable.execution.errors import (
    ExecutionCancelled,
    IdempotencyConflict,
    RetryableExecutionError,
)

FR_EXEC_001 = "FR-EXEC-001"
FR_EXEC_004 = "FR-EXEC-004"
FR_EXEC_006 = "FR-EXEC-006"
FR_EXEC_007 = "FR-EXEC-007"
FR_EXEC_008 = "FR-EXEC-008"


class CountingExecutor:
    def __init__(self, failures: int = 0) -> None:
        self.calls = 0
        self.failures = failures

    def execute(self, payload: dict[str, object]) -> object:
        self.calls += 1
        if self.calls <= self.failures:
            raise RetryableExecutionError("temporary")
        return {"answer": payload["value"]}


class ExecutionEngineTests(unittest.TestCase):
    def test_phase_7_rejects_invalid_requests_and_duplicate_executors(self) -> None:
        with self.assertRaises(ValueError):
            ExecutionRequest("", {}, "key")
        with self.assertRaises(ValueError):
            ExecutionRequest("test", {}, "key", max_attempts=0)
        engine = ExecutionEngine()
        engine.register("test", CountingExecutor())
        with self.assertRaises(ValueError):
            engine.register("test", CountingExecutor())
        with self.assertRaises(ValueError):
            engine.run(ExecutionRequest("missing", {}, "key"))

    def test_phase_7_is_idempotent_and_content_addressed(self) -> None:
        executor = CountingExecutor()
        engine = ExecutionEngine()
        engine.register("test", executor)
        request = ExecutionRequest("test", {"value": 42}, "stable-key")

        first = engine.run(request)
        second = engine.run(request)

        self.assertEqual(first, second)
        self.assertEqual(len(first.artifact_id), 64)
        self.assertEqual(executor.calls, 1)

    def test_phase_7_idempotency_key_cannot_hide_different_input(self) -> None:
        engine = ExecutionEngine()
        engine.register("test", CountingExecutor())
        engine.run(ExecutionRequest("test", {"value": 1}, "same"))
        with self.assertRaises(IdempotencyConflict):
            engine.run(ExecutionRequest("test", {"value": 2}, "same"))

    def test_phase_7_retries_only_explicit_retryable_failures(self) -> None:
        executor = CountingExecutor(failures=2)
        engine = ExecutionEngine()
        engine.register("test", executor)
        artifact = engine.run(ExecutionRequest("test", {"value": 42}, "retry", max_attempts=3))
        self.assertEqual(artifact.attempts, 3)
        self.assertEqual(executor.calls, 3)
        with self.assertRaises(RetryableExecutionError):
            another = ExecutionEngine()
            another.register("test", CountingExecutor(failures=2))
            another.run(ExecutionRequest("test", {"value": 42}, "exhaust", max_attempts=1))

    def test_phase_7_cancellation_prevents_execution(self) -> None:
        executor = CountingExecutor()
        engine = ExecutionEngine()
        engine.register("test", executor)
        token = CancellationToken()
        token.cancel()
        with self.assertRaises(ExecutionCancelled):
            engine.run(
                ExecutionRequest("test", {"value": 42}, "cancelled"),
                cancellation=token,
            )
        self.assertEqual(executor.calls, 0)


if __name__ == "__main__":
    unittest.main()
