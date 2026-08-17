from __future__ import annotations

from pathlib import Path

from answerable.application.spec_scaffold import guess_roles, scaffold_question
from answerable.ingestion.files import FileInspector

_CSV = """customer_id,acquisition_date,acquisition_channel,campaign_exposed,retained_90d
c001,2025-01-01T00:00:00+00:00,organic,true,true
c002,2025-01-02T00:00:00+00:00,paid,false,false
c003,2025-01-03T00:00:00+00:00,organic,true,true
c004,2025-01-04T00:00:00+00:00,paid,false,false
"""


def _write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "customers.csv"
    path.write_text(_CSV, encoding="utf-8")
    return path


def test_guess_roles_finds_entity_time_treatment_and_boolean_outcome(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    inspector = FileInspector()
    try:
        snapshot = inspector.inspect(path)
    finally:
        inspector.close()

    roles = guess_roles(snapshot)

    assert roles.entity_column == "customer_id"
    assert roles.event_time_column == "acquisition_date"
    assert roles.treatment_column == "campaign_exposed"
    assert roles.outcome_column == "retained_90d"
    assert not roles.unresolved


def test_scaffold_question_writes_yaml_with_guesses_and_todo_markers(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)

    text = scaffold_question(path)

    assert "entity_column: customer_id" in text
    assert "treatment_column: campaign_exposed" in text
    assert "outcome_column: retained_90d" in text
    assert "TODO" in text  # a human still has to decide the question and claims
    assert "Could not guess" not in text


def test_scaffold_question_flags_unresolved_roles(tmp_path: Path) -> None:
    path = tmp_path / "flat.csv"
    path.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")

    text = scaffold_question(path)

    # No date/time-typed or date-named column exists, so event_time_column
    # cannot be guessed and must fall through to a TODO the human fills in.
    assert "Could not guess: event_time_column" in text
    assert "event_time_column: TODO" in text
