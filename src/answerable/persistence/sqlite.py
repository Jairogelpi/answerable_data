from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast

from answerable.domain.assessment import Assessment, AuditEvent
from answerable.domain.lifecycle import AssessmentState
from answerable.domain.serialization import canonical_json
from answerable.persistence.errors import (
    ConcurrencyConflict,
    ImmutableRecordError,
    RecordAlreadyExists,
    RecordNotFound,
)


class SQLiteAssessmentRepository:
    def __init__(self, path: Path | str) -> None:
        self._connection = sqlite3.connect(str(path), isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def _migrate(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS assessment_versions (
                assessment_id TEXT NOT NULL,
                version INTEGER NOT NULL CHECK (version > 0),
                state TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (assessment_id, version)
            );
            CREATE TABLE IF NOT EXISTS assessment_heads (
                assessment_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                state TEXT NOT NULL,
                FOREIGN KEY (assessment_id, version)
                  REFERENCES assessment_versions(assessment_id, version)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                previous_version INTEGER,
                new_version INTEGER NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS audit_assessment_idx
              ON audit_events(assessment_id, occurred_at, event_id);
            CREATE TABLE IF NOT EXISTS idempotency (
                idempotency_key TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                response_json TEXT NOT NULL
            );
            """
        )

    def close(self) -> None:
        self._connection.close()

    def add(self, assessment: Assessment) -> None:
        try:
            with self._connection:
                self._insert_version(assessment)
                self._connection.execute(
                    "INSERT INTO assessment_heads(assessment_id, version, state) VALUES (?, ?, ?)",
                    (assessment.assessment_id, assessment.version, assessment.state.value),
                )
        except sqlite3.IntegrityError as error:
            raise RecordAlreadyExists(assessment.assessment_id) from error

    def save(self, assessment: Assessment, *, expected_version: int) -> None:
        with self._connection:
            head = self._head(assessment.assessment_id)
            if int(head["version"]) != expected_version:
                raise ConcurrencyConflict(
                    f"expected version {expected_version}, found {head['version']}"
                )
            if AssessmentState(str(head["state"])) in {
                AssessmentState.ISSUED,
                AssessmentState.SUPERSEDED,
            }:
                raise ImmutableRecordError("issued and superseded assessments are immutable")
            if assessment.version != expected_version + 1:
                raise ConcurrencyConflict("new version must increment expected version by one")
            self._insert_version(assessment)
            cursor = self._connection.execute(
                """
                UPDATE assessment_heads
                SET version = ?, state = ?
                WHERE assessment_id = ? AND version = ?
                """,
                (
                    assessment.version,
                    assessment.state.value,
                    assessment.assessment_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyConflict("assessment head changed during save")

    def get(self, assessment_id: str) -> Assessment:
        head = self._head(assessment_id)
        row = self._connection.execute(
            """
            SELECT payload FROM assessment_versions
            WHERE assessment_id = ? AND version = ?
            """,
            (assessment_id, head["version"]),
        ).fetchone()
        if row is None:
            raise RecordNotFound(assessment_id)
        return self._assessment_from_json(str(row["payload"]))

    def history(self, assessment_id: str) -> list[Assessment]:
        rows = self._connection.execute(
            """
            SELECT payload FROM assessment_versions
            WHERE assessment_id = ?
            ORDER BY version
            """,
            (assessment_id,),
        ).fetchall()
        if not rows:
            raise RecordNotFound(assessment_id)
        return [self._assessment_from_json(str(row["payload"])) for row in rows]

    def append_audit_event(self, event: AuditEvent) -> None:
        self._connection.execute(
            """
            INSERT INTO audit_events(
                event_id, assessment_id, actor_id, action,
                previous_version, new_version, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.assessment_id,
                event.actor_id,
                event.action,
                event.previous_version,
                event.new_version,
                event.occurred_at.isoformat(),
            ),
        )

    def list_audit_events(self, assessment_id: str) -> list[AuditEvent]:
        rows = self._connection.execute(
            """
            SELECT * FROM audit_events
            WHERE assessment_id = ?
            ORDER BY occurred_at, event_id
            """,
            (assessment_id,),
        ).fetchall()
        return [
            AuditEvent(
                event_id=str(row["event_id"]),
                assessment_id=str(row["assessment_id"]),
                actor_id=str(row["actor_id"]),
                action=str(row["action"]),
                previous_version=(
                    int(row["previous_version"]) if row["previous_version"] is not None else None
                ),
                new_version=int(row["new_version"]),
                occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
            )
            for row in rows
        ]

    def claim_idempotency(self, idempotency_key: str, request_hash: str, response_json: str) -> str:
        with self._connection:
            row = self._connection.execute(
                "SELECT request_hash, response_json FROM idempotency WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is not None:
                if str(row["request_hash"]) != request_hash:
                    raise ConcurrencyConflict("idempotency key was reused for a different request")
                return str(row["response_json"])
            self._connection.execute(
                """
                INSERT INTO idempotency(idempotency_key, request_hash, response_json)
                VALUES (?, ?, ?)
                """,
                (idempotency_key, request_hash, response_json),
            )
            return response_json

    def get_idempotency(self, idempotency_key: str, request_hash: str) -> str | None:
        row = self._connection.execute(
            "SELECT request_hash, response_json FROM idempotency WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            return None
        if str(row["request_hash"]) != request_hash:
            raise ConcurrencyConflict("idempotency key was reused for a different request")
        return str(row["response_json"])

    def _head(self, assessment_id: str) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT version, state FROM assessment_heads WHERE assessment_id = ?",
            (assessment_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFound(assessment_id)
        return cast(sqlite3.Row, row)

    def _insert_version(self, assessment: Assessment) -> None:
        self._connection.execute(
            """
            INSERT INTO assessment_versions(
                assessment_id, version, state, payload, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                assessment.assessment_id,
                assessment.version,
                assessment.state.value,
                canonical_json(assessment),
                assessment.updated_at.isoformat(),
            ),
        )

    @staticmethod
    def _assessment_from_json(payload: str) -> Assessment:
        value = json.loads(payload)
        return Assessment(
            assessment_id=value["assessment_id"],
            workspace_id=value["workspace_id"],
            created_by=value["created_by"],
            state=AssessmentState(value["state"]),
            version=value["version"],
            created_at=datetime.fromisoformat(value["created_at"]),
            updated_at=datetime.fromisoformat(value["updated_at"]),
            question_contract_id=value["question_contract_id"],
            artifact_ids=tuple(value["artifact_ids"]),
            cancelled=value["cancelled"],
        )
