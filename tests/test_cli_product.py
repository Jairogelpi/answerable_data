from __future__ import annotations

import json
from pathlib import Path

from answerable.cli import main


def test_doctor_human_output_reports_ready(capsys: object) -> None:
    code = main(("doctor",))
    output = capsys.readouterr().out

    assert code == 0
    assert "Status: ready" in output
    assert "duckdb: ok" in output
    assert "sqlglot: ok" in output
    assert "yaml: ok" in output


def test_doctor_json_is_machine_readable(capsys: object) -> None:
    code = main(("--json", "doctor"))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ready"
    assert payload["command"] == "doctor"
    assert payload["demos"] == ["causal", "grain", "maturity"]


def test_demo_human_output_surfaces_claim_boundaries(tmp_path: Path, capsys: object) -> None:
    code = main(("demo", "causal", "--output", str(tmp_path / "demo")))
    output = capsys.readouterr().out

    assert code == 0
    assert "FUNDAMENTALLY_UNIDENTIFIABLE" in output
    assert "positivity_violation" in output
    assert "Supported claims:" in output
    assert "Unsupported claims:" in output
    assert "warrant.md" in output


def test_demo_json_returns_expected_signal(tmp_path: Path, capsys: object) -> None:
    code = main(
        ("--json", "demo", "maturity", "--output", str(tmp_path / "demo-maturity"))
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["case"] == "maturity"
    assert payload["expected_signal"] == "immature_cohort"
    assert "immature_cohort" in payload["blockers"]
    assert Path(payload["artifacts"]["warrant"]).is_file()
