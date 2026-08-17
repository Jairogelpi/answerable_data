"""Real handlers behind the MCP tool contract.

`interfaces/mcp.py`'s `MCPServer` is a disclosure-scoping dispatcher over an
arbitrary handler dict; this module is the arbitrary handler dict, backed by
the same code paths the CLI uses (`AssessmentRunner`, `FileInspector`,
`scaffold_question`, `verify_warrant`). No tool here fabricates a result --
each one reads or computes something a real assessment already produces.

`inspect_data` never returns row-level data (`FileInspector` only profiles
columns), so it is safe to disclose at `MCPDisclosure.METADATA_ONLY` by
construction -- there's no raw-rows branch to gate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


def _read_artifact(output_dir: object, name: str) -> object:
    path = Path(str(output_dir)) / name
    if not path.is_file():
        return {"error": f"{name} not found in {output_dir}. Run assess_answerability first."}
    return json.loads(path.read_text(encoding="utf-8"))


def assess_answerability(args: dict[str, object]) -> dict[str, object]:
    from answerable.application.assessment_runner import AssessmentRunner
    from answerable.application.spec_loader import load_spec

    data = args["data"]
    paths = tuple(Path(str(item)) for item in (data if isinstance(data, list) else [data]))
    run = AssessmentRunner().run(
        data_sources=paths,
        spec=load_spec(Path(str(args["question"]))),
        output_directory=Path(str(args["output"])),
    )
    return {
        "assessment_id": run.assessment_id,
        "verdict": run.verdict.value,
        "blockers": [
            {"finding_id": item.finding_id, "message": item.message, "category": item.category}
            for item in run.blockers
        ],
        "allowed_claims": list(run.allowed_claims),
        "forbidden_claims": list(run.forbidden_claims),
        "artifacts": {name: str(path) for name, path in sorted(run.artifacts.items())},
    }


def inspect_data(args: dict[str, object]) -> dict[str, object]:
    from answerable.ingestion.files import FileInspector

    inspector = FileInspector()
    try:
        snapshot = inspector.inspect(Path(str(args["data"])))
    finally:
        inspector.close()
    return {
        "row_count": snapshot.row_count,
        "fingerprint": snapshot.fingerprint,
        "columns": [
            {
                "name": column.name,
                "physical_type": column.physical_type,
                "null_count": column.null_count,
                "distinct_count": column.distinct_count,
            }
            for column in snapshot.profile.columns
        ],
    }


def frame_question(args: dict[str, object]) -> dict[str, object]:
    from answerable.application.spec_scaffold import guess_roles, scaffold_question
    from answerable.ingestion.files import FileInspector

    data_path = Path(str(args["data"]))
    inspector = FileInspector()
    try:
        snapshot = inspector.inspect(data_path)
    finally:
        inspector.close()
    roles = guess_roles(snapshot)
    text = scaffold_question(data_path)
    output = args.get("output")
    if output:
        Path(str(output)).write_text(text, encoding="utf-8")
    return {
        "question_yaml": text,
        "guessed": {
            "entity_column": roles.entity_column,
            "event_time_column": roles.event_time_column,
            "treatment_column": roles.treatment_column,
            "outcome_column": roles.outcome_column,
            "covariate_columns": list(roles.covariate_columns),
        },
        "unresolved": list(roles.unresolved),
    }


def verify_warrant(args: dict[str, object]) -> dict[str, object]:
    from answerable.application.assessment_runner import load_warrant
    from answerable.public import verify_warrant as _verify

    path = Path(str(args["warrant"]))
    valid = _verify(load_warrant(path))
    return {"warrant": str(path), "valid": valid}


def get_assessment(args: dict[str, object]) -> dict[str, object]:
    output = args["output"]
    return {
        "verdict": _read_artifact(output, "verdict.json"),
        "warrant": _read_artifact(output, "warrant.json"),
    }


def explain_finding(args: dict[str, object]) -> dict[str, object]:
    findings = _read_artifact(args["output"], "findings.json")
    if isinstance(findings, dict) and "error" in findings:
        return findings
    finding_id = str(args["finding_id"])
    items = findings if isinstance(findings, list) else []
    for item in items:
        if isinstance(item, dict) and item.get("code") == finding_id:
            return dict(item)
    return {"error": f"no finding with code {finding_id!r} in this assessment"}


def design_missing_evidence_plan(args: dict[str, object]) -> dict[str, object]:
    result = _read_artifact(args["output"], "repair_plan.json")
    return result if isinstance(result, dict) else {"error": "repair_plan.json was not an object"}


def generate_analysis_plan(args: dict[str, object]) -> dict[str, object]:
    result = _read_artifact(args["output"], "check_plan.json")
    return result if isinstance(result, dict) else {"error": "check_plan.json was not an object"}


HANDLERS: dict[str, Callable[[dict[str, object]], dict[str, object]]] = {
    "frame_question": frame_question,
    "inspect_data": inspect_data,
    "assess_answerability": assess_answerability,
    "get_assessment": get_assessment,
    "explain_finding": explain_finding,
    "design_missing_evidence_plan": design_missing_evidence_plan,
    "generate_analysis_plan": generate_analysis_plan,
    "verify_warrant": verify_warrant,
}

__all__ = [
    "HANDLERS",
    "assess_answerability",
    "design_missing_evidence_plan",
    "explain_finding",
    "frame_question",
    "generate_analysis_plan",
    "get_assessment",
    "inspect_data",
    "verify_warrant",
]
