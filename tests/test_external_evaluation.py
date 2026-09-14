"""INV-002 / BENCH: retain valid claims and audit real mediated tool calls."""

import json
import sys
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_external_agents import build_context, paired_metrics, parse_decision, run_case
from evaluate_external import evaluate, materialize, metrics


def test_BENCH_external_data_keeps_valid_claims_and_rejects_invalid(tmp_path: Path) -> None:
    report = evaluate(tmp_path)
    assert report["metrics"] == {
        "total": 12,
        "valid_claims": 4,
        "invalid_claims": 8,
        "false_blocks": 0,
        "unsafe_allows": 0,
        "false_block_rate": 0.0,
        "unsafe_allow_rate": 0.0,
        "errors": 0,
        "release_false_blocks": 0,
    }
    for row in report["records"]:
        if row["variant"] == "observed":
            assert row["expected_means"] == pytest.approx(row["observed_means"])


def test_BENCH_failure_metrics_do_not_hide_unparseable_answers() -> None:
    assert metrics([])["false_block_rate"] is None
    records = [
        {"expected_allow": True, "allowed": False},
        {"expected_allow": False, "allowed": True},
        {"expected_allow": True, "allowed": None, "error": "timeout"},
    ]
    assert metrics(records)["false_blocks"] == 1
    assert metrics(records)["unsafe_allows"] == 1
    assert metrics(records)["errors"] == 1
    assert paired_metrics([])["accuracy_delta"] is None


def test_BENCH_context_excludes_oracle_and_tool_arm_executes_real_handler(tmp_path: Path) -> None:
    case = materialize(tmp_path)[1]
    folder = tmp_path / "cases" / case["case_id"]
    assert "expected_allow" not in json.dumps(build_context(folder))
    replies = [
        CompletedProcess([], 0, "CALL_ANSWERABLE", ""),
        CompletedProcess([], 0, "Evidence is missing.\nDECISION: BLOCK", ""),
    ]
    with patch("compare_external_agents.subprocess.run", side_effect=replies):
        result = run_case(["test-only-adapter"], "test-double", folder, "tool")
    assert result["allowed"] is False
    assert len(result["tool_calls"]) == 1
    assert (folder / "tool-assessment/warrant.json").is_file()
    assert "identification_evidence_missing" in json.dumps(result["tool_calls"])
    assert "Tool:" in result["transcript"][1]["prompt"]


@pytest.mark.parametrize(
    "response", ["DECISION: ALLOW\nDECISION: BLOCK", "BLOCK", "DECISION: ALLOW\nextra"]
)
def test_BENCH_ambiguous_outputs_are_errors(response: str) -> None:
    assert parse_decision(response) is None


def test_BENCH_alone_cannot_request_tool_and_adapter_errors_are_recorded(tmp_path: Path) -> None:
    case = materialize(tmp_path)[0]
    folder = tmp_path / "cases" / case["case_id"]
    for response in (
        CompletedProcess([], 0, "CALL_ANSWERABLE", ""),
        CompletedProcess([], 1, "DECISION: ALLOW", "error"),
    ):
        with patch("compare_external_agents.subprocess.run", return_value=response):
            result = run_case(["test-only-adapter"], "test-double", folder, "alone")
        assert result["allowed"] is None
        assert result["error"]
        assert not result["tool_calls"]
    with patch("compare_external_agents.subprocess.run", side_effect=TimeoutExpired("adapter", 1)):
        assert run_case(["test-only-adapter"], "test-double", folder, "tool")["allowed"] is None


def test_BENCH_paired_scores_include_regressions_and_exclude_incomplete_pairs() -> None:
    records = []
    for case, expected, before, after in [
        ("improves", True, False, True),
        ("regresses", False, False, True),
        ("missing", True, None, True),
    ]:
        for arm, answer in [("alone", before), ("tool", after)]:
            records.append(
                {
                    "case_id": case,
                    "repetition": 0,
                    "arm": arm,
                    "expected_allow": expected,
                    "allowed": answer,
                    "tool_calls": [],
                }
            )
    result = paired_metrics(records)
    assert result["complete_pairs"] == 2
    assert result["improved"] == result["regressed"] == 1
    assert result["accuracy_delta"] == 0
