from __future__ import annotations

from pathlib import Path

from answerable.interfaces.mcp_handlers import (
    HANDLERS,
    assess_answerability,
    design_missing_evidence_plan,
    explain_finding,
    frame_question,
    generate_analysis_plan,
    get_assessment,
    inspect_data,
    verify_warrant,
)

_EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "campaign_retention"


def test_handlers_registry_matches_the_mcp_contract() -> None:
    from answerable.interfaces.mcp import MCPServer

    # MCPServer.__init__ raises on an unknown tool name, so this is a real
    # assertion that every handler's name is one MCPServer will accept.
    MCPServer(HANDLERS)
    assert set(HANDLERS) == MCPServer.TOOLS


def test_inspect_data_profiles_columns_without_row_values() -> None:
    result = inspect_data({"data": str(_EXAMPLE / "customers.csv")})

    assert result["row_count"] == 50
    names = {column["name"] for column in result["columns"]}  # type: ignore[union-attr]
    assert "customer_id" in names
    assert "rows" not in result


def test_frame_question_guesses_the_real_example_roles() -> None:
    result = frame_question({"data": str(_EXAMPLE / "customers.csv")})

    assert result["guessed"] == {
        "entity_column": "customer_id",
        "event_time_column": "acquisition_date",
        "treatment_column": "campaign_exposed",
        "outcome_column": "retained_90d",
        "covariate_columns": ["acquisition_channel"],
    }
    assert not result["unresolved"]


def test_full_lifecycle_assess_then_read_back(tmp_path: Path) -> None:
    output = tmp_path / "run"
    run = assess_answerability(
        {
            "data": [str(_EXAMPLE / "customers.csv")],
            "question": str(_EXAMPLE / "question.yaml"),
            "output": str(output),
        }
    )

    assert run["verdict"] == "FUNDAMENTALLY_UNIDENTIFIABLE"
    blocker_ids = {item["finding_id"] for item in run["blockers"]}  # type: ignore[union-attr]
    assert "positivity_violation" in blocker_ids

    read_back = get_assessment({"output": str(output)})
    assert read_back["verdict"]["verdict"] == "FUNDAMENTALLY_UNIDENTIFIABLE"  # type: ignore[index]

    finding = explain_finding({"output": str(output), "finding_id": "positivity_violation"})
    assert "message" in finding

    missing = explain_finding({"output": str(output), "finding_id": "not_a_real_code"})
    assert "error" in missing

    plan = design_missing_evidence_plan({"output": str(output)})
    assert "candidates" in plan

    checks = generate_analysis_plan({"output": str(output)})
    assert "checks" in checks

    warrant_path = str(run["artifacts"]["warrant"])  # type: ignore[index]
    verified = verify_warrant({"warrant": warrant_path})
    assert verified == {"warrant": warrant_path, "valid": True}


def test_get_assessment_reports_missing_artifacts_instead_of_raising(tmp_path: Path) -> None:
    result = get_assessment({"output": str(tmp_path)})

    assert "error" in result["verdict"]  # type: ignore[operator]
