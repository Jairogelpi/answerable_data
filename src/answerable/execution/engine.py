from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from answerable.execution.errors import (
    ExecutionCancelled,
    IdempotencyConflict,
    RetryableExecutionError,
)


class ExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    executor: str
    payload: dict[str, object]
    idempotency_key: str
    max_attempts: int = 1

    def __post_init__(self) -> None:
        if not self.executor or not self.idempotency_key:
            raise ValueError("executor and idempotency_key are required")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            {"executor": self.executor, "payload": self.payload},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutionArtifact:
    artifact_id: str
    request_fingerprint: str
    executor: str
    status: ExecutionStatus
    attempts: int
    result: object


class Executor(Protocol):
    def execute(self, payload: dict[str, object]) -> object: ...


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ExecutionCancelled("execution was cancelled")


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._artifacts: dict[str, ExecutionArtifact] = {}
        self._idempotency: dict[str, tuple[str, str]] = {}

    def resolve(self, key: str, fingerprint: str) -> ExecutionArtifact | None:
        existing = self._idempotency.get(key)
        if existing is None:
            return None
        existing_fingerprint, artifact_id = existing
        if existing_fingerprint != fingerprint:
            raise IdempotencyConflict("idempotency key was reused with a different request")
        return self._artifacts[artifact_id]

    def put(self, key: str, artifact: ExecutionArtifact) -> None:
        self._artifacts.setdefault(artifact.artifact_id, artifact)
        self._idempotency[key] = (artifact.request_fingerprint, artifact.artifact_id)


class ExecutionEngine:
    VERSION = "1"

    def __init__(self, store: InMemoryArtifactStore | None = None) -> None:
        self._executors: dict[str, Executor] = {}
        self._store = store or InMemoryArtifactStore()

    def register(self, name: str, executor: Executor) -> None:
        if not name or name in self._executors:
            raise ValueError("executor name must be non-empty and unique")
        self._executors[name] = executor

    def run(
        self,
        request: ExecutionRequest,
        *,
        cancellation: CancellationToken | None = None,
    ) -> ExecutionArtifact:
        cached = self._store.resolve(request.idempotency_key, request.fingerprint)
        if cached is not None:
            return cached
        if request.executor not in self._executors:
            raise ValueError(f"unknown executor: {request.executor}")
        token = cancellation or CancellationToken()
        attempts = 0
        while True:
            token.raise_if_cancelled()
            attempts += 1
            try:
                result = self._executors[request.executor].execute(request.payload)
                token.raise_if_cancelled()
                artifact = self._artifact(request, attempts, result)
                self._store.put(request.idempotency_key, artifact)
                return artifact
            except RetryableExecutionError:
                if attempts >= request.max_attempts:
                    raise

    def _artifact(
        self, request: ExecutionRequest, attempts: int, result: object
    ) -> ExecutionArtifact:
        content = {
            "engine_version": self.VERSION,
            "executor": request.executor,
            "request_fingerprint": request.fingerprint,
            "attempts": attempts,
            "result": result,
        }
        artifact_id = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return ExecutionArtifact(
            artifact_id=artifact_id,
            request_fingerprint=request.fingerprint,
            executor=request.executor,
            status=ExecutionStatus.SUCCEEDED,
            attempts=attempts,
            result=result,
        )
