from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class TenantContext:
    tenant_id: str
    actor_id: str
    roles: frozenset[str]

    def require(self, role: str) -> None:
        if role not in self.roles:
            raise PermissionError(f"role required: {role}")


class SecretStore:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str], str] = {}

    def put(self, tenant_id: str, name: str, value: str) -> None:
        if not tenant_id or not name or not value:
            raise ValueError("tenant, name, and secret are required")
        self._values[(tenant_id, name)] = value

    def resolve(self, context: TenantContext, name: str) -> str:
        context.require("secret_reader")
        return self._values[(context.tenant_id, name)]

    def redact(self, text: str) -> str:
        for value in self._values.values():
            text = text.replace(value, "[REDACTED]")
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
        return text


@dataclass(frozen=True, slots=True)
class AuditEntry:
    tenant_id: str
    actor_id: str
    action: str
    resource_id: str
    occurred_at: datetime
    previous_hash: str
    entry_hash: str


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, context: TenantContext, action: str, resource_id: str) -> AuditEntry:
        previous = self._entries[-1].entry_hash if self._entries else "0" * 64
        occurred = datetime.now(UTC)
        canonical = json.dumps(
            [
                context.tenant_id,
                context.actor_id,
                action,
                resource_id,
                occurred.isoformat(),
                previous,
            ],
            separators=(",", ":"),
        )
        entry = AuditEntry(
            context.tenant_id,
            context.actor_id,
            action,
            resource_id,
            occurred,
            previous,
            hashlib.sha256(canonical.encode()).hexdigest(),
        )
        self._entries.append(entry)
        return entry

    def for_tenant(self, context: TenantContext) -> tuple[AuditEntry, ...]:
        return tuple(entry for entry in self._entries if entry.tenant_id == context.tenant_id)


class GovernanceStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], tuple[datetime, dict[str, object]]] = {}

    def put(self, context: TenantContext, resource_id: str, value: dict[str, object]) -> None:
        context.require("writer")
        self._records[(context.tenant_id, resource_id)] = (datetime.now(UTC), dict(value))

    def get(self, context: TenantContext, resource_id: str) -> dict[str, object]:
        context.require("reader")
        return dict(self._records[(context.tenant_id, resource_id)][1])

    def apply_retention(
        self, context: TenantContext, *, older_than: timedelta, now: datetime | None = None
    ) -> int:
        context.require("retention_admin")
        cutoff = (now or datetime.now(UTC)) - older_than
        keys = [
            key
            for key, (created, _) in self._records.items()
            if key[0] == context.tenant_id and created < cutoff
        ]
        for key in keys:
            del self._records[key]
        return len(keys)

    def backup(self, context: TenantContext) -> str:
        context.require("backup_admin")
        records = {
            resource: value
            for (tenant, resource), (_, value) in self._records.items()
            if tenant == context.tenant_id
        }
        return json.dumps(records, sort_keys=True, separators=(",", ":"))

    def restore(self, context: TenantContext, backup: str) -> None:
        context.require("backup_admin")
        decoded = json.loads(backup)
        if not isinstance(decoded, dict):
            raise ValueError("invalid backup")
        for resource, value in decoded.items():
            if not isinstance(value, dict):
                raise ValueError("invalid backup resource")
            self._records[(context.tenant_id, resource)] = (datetime.now(UTC), value)
