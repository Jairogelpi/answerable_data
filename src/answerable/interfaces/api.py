from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProblemDetail:
    type: str
    title: str
    status: int
    detail: str
    code: str


@dataclass(frozen=True, slots=True)
class ApiResponse:
    status: int
    body: dict[str, object]
    etag: str | None = None


class ApiService:
    BASE_PATH = "/v1"

    def __init__(self) -> None:
        self._idempotency: dict[str, tuple[dict[str, object], ApiResponse]] = {}
        self._resources: dict[str, tuple[int, dict[str, object]]] = {}

    def create(
        self, resource_id: str, body: dict[str, object], *, idempotency_key: str
    ) -> ApiResponse:
        if not idempotency_key:
            raise ValueError("idempotency key is required")
        previous = self._idempotency.get(idempotency_key)
        if previous:
            old_body, response = previous
            if old_body != body:
                return self.problem(
                    "concurrency_conflict", 409, "Idempotency key reused with different content"
                )
            return response
        self._resources[resource_id] = (1, dict(body))
        response = ApiResponse(201, {"id": resource_id, **body}, '"1"')
        self._idempotency[idempotency_key] = (dict(body), response)
        return response

    def patch(self, resource_id: str, body: dict[str, object], *, if_match: str) -> ApiResponse:
        version, current = self._resources[resource_id]
        if if_match != f'"{version}"':
            return self.problem("concurrency_conflict", 409, "ETag does not match current version")
        updated = {**current, **body}
        self._resources[resource_id] = (version + 1, updated)
        return ApiResponse(200, {"id": resource_id, **updated}, f'"{version + 1}"')

    @staticmethod
    def problem(code: str, status: int, detail: str) -> ApiResponse:
        problem = ProblemDetail(
            f"https://answerable.dev/problems/{code}",
            code.replace("_", " ").title(),
            status,
            detail,
            code,
        )
        return ApiResponse(
            status,
            {
                "type": problem.type,
                "title": problem.title,
                "status": status,
                "detail": detail,
                "code": code,
            },
        )
