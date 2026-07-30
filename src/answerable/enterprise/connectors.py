from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ConnectorCapabilities:
    catalog: bool
    read_only_query: bool
    pushdown: bool
    cancellation: bool


class EnterpriseConnector(Protocol):
    @property
    def capabilities(self) -> ConnectorCapabilities: ...
    def test(self) -> bool: ...
    def catalog(self) -> tuple[str, ...]: ...
    def query(self, sql: str, *, max_rows: int) -> tuple[dict[str, object], ...]: ...


class ConnectorConformance:
    def validate(self, connector: EnterpriseConnector) -> None:
        if not connector.test():
            raise ValueError("connector health check failed")
        if not connector.capabilities.catalog or not connector.capabilities.read_only_query:
            raise ValueError("connector lacks required read-only capabilities")
        if not connector.catalog():
            raise ValueError("connector catalog is empty")
        try:
            connector.query("DELETE FROM protected", max_rows=1)
        except (PermissionError, ValueError):
            return
        raise ValueError("connector accepted a mutation")
