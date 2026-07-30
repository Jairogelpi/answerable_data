from __future__ import annotations

import unittest

from answerable.enterprise.connectors import ConnectorCapabilities, ConnectorConformance
from answerable.enterprise.governance import AuditLog, GovernanceStore, SecretStore, TenantContext

SEC_001 = "SEC-001"
SEC_002 = "SEC-002"
SEC_008 = "SEC-008"
SEC_009 = "SEC-009"
SEC_010 = "SEC-010"


class FakeConnector:
    capabilities = ConnectorCapabilities(True, True, True, True)

    def test(self) -> bool:
        return True

    def catalog(self) -> tuple[str, ...]:
        return ("orders",)

    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]:
        del max_rows
        if not sql.lstrip().upper().startswith("SELECT"):
            raise PermissionError("read only")
        return ({"id": 1},)


class EnterpriseGovernanceTests(unittest.TestCase):
    def test_phase_17_connector_conformance_requires_read_only_behavior(self) -> None:
        ConnectorConformance().validate(FakeConnector())

    def test_phase_17_tenant_isolation_and_rbac(self) -> None:
        store = GovernanceStore()
        a = TenantContext("a", "u", frozenset({"writer", "reader", "backup_admin"}))
        b = TenantContext("b", "u", frozenset({"reader", "backup_admin"}))
        store.put(a, "r1", {"value": 1})
        self.assertEqual(store.get(a, "r1"), {"value": 1})
        with self.assertRaises(KeyError):
            store.get(b, "r1")
        with self.assertRaises(PermissionError):
            store.put(b, "r2", {})

    def test_phase_17_secrets_are_redacted_and_audit_is_tenant_scoped(self) -> None:
        secrets = SecretStore()
        context = TenantContext("a", "u", frozenset({"secret_reader"}))
        secrets.put("a", "warehouse", "top-secret")
        self.assertEqual(secrets.resolve(context, "warehouse"), "top-secret")
        self.assertEqual(secrets.redact("top-secret a@b.com"), "[REDACTED] [EMAIL]")
        audit = AuditLog()
        first = audit.append(context, "read", "source")
        second = audit.append(TenantContext("b", "x", frozenset()), "read", "other")
        self.assertEqual(second.previous_hash, first.entry_hash)
        self.assertEqual(audit.for_tenant(context), (first,))

    def test_phase_17_backup_restore_is_verified(self) -> None:
        context = TenantContext("a", "u", frozenset({"writer", "reader", "backup_admin"}))
        original = GovernanceStore()
        original.put(context, "warrant", {"hash": "abc"})
        backup = original.backup(context)
        restored = GovernanceStore()
        restored.restore(context, backup)
        self.assertEqual(restored.get(context, "warrant"), {"hash": "abc"})


if __name__ == "__main__":
    unittest.main()
