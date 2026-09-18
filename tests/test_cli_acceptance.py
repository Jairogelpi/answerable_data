"""FR-CLI-001: a successful process must reflect an actual operation."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.spec_loader import load_spec
from answerable.cli import COMMANDS, build_parser

ENTRY = [sys.executable, "-c", "from answerable.cli import main; raise SystemExit(main())"]
UNAVAILABLE = [
    ("frame",),
    ("plan",),
    ("execute",),
    ("inspect",),
    ("source", "add"),
    ("source", "test"),
]

# Every top-level subcommand argparse knows about must be accounted for here as either
# implemented (has a real handler in cli.main and its own acceptance test) or reserved
# (deliberately unavailable). A command that appears in neither is exactly the bug class
# that shipped silently before: main() falls through and cannot know whether the new
# name was supposed to do something. Line coverage cannot catch that -- the fallthrough
# branch is still "covered", it's just covered doing the wrong thing. This test makes
# adding a new subcommand without wiring it a hard failure instead of a silent gap.
IMPLEMENTED_COMMANDS = {"doctor", "init", "demo", "benchmark", "assess", "warrant", "mcp"}
RESERVED_COMMANDS = set(COMMANDS) | {"source"}


def _registered_subcommands() -> set[str]:
    subparsers_action = next(
        action
        for action in build_parser()._subparsers._group_actions  # type: ignore[union-attr]
        if hasattr(action, "choices")
    )
    choices = subparsers_action.choices
    assert choices is not None
    return set(choices)


def test_FR_CLI_001_every_registered_subcommand_is_classified() -> None:
    registered = _registered_subcommands()
    known = IMPLEMENTED_COMMANDS | RESERVED_COMMANDS
    unclassified = registered - known
    assert not unclassified, (
        f"{unclassified} are registered in build_parser() but not classified as "
        "implemented or reserved in this test file -- add real dispatch + an "
        "acceptance test, or add to RESERVED_COMMANDS if deliberately unavailable."
    )
    stale = known - registered
    assert not stale, f"{stale} are classified here but no longer registered in build_parser()"


@pytest.mark.parametrize("args", UNAVAILABLE)
@pytest.mark.parametrize("json_mode", [False, True])
def test_FR_CLI_001_unavailable_commands_fail_without_side_effects(
    tmp_path: Path, args: tuple[str, ...], json_mode: bool
) -> None:
    result = subprocess.run(
        [*ENTRY, *(["--json"] if json_mode else []), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 5
    assert list(tmp_path.iterdir()) == []
    if json_mode:
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert payload["code"] == "command_unavailable"
        assert result.stderr == ""
    else:
        assert result.stdout == ""
        assert "not available" in result.stderr


@pytest.mark.parametrize("json_mode", [False, True])
def test_FR_CLI_001_verify_requires_a_file(tmp_path: Path, json_mode: bool) -> None:
    result = subprocess.run(
        [*ENTRY, *(["--json"] if json_mode else []), "warrant", "verify"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    if json_mode:
        payload = json.loads(result.stdout)
        assert payload["code"] == "warrant_required"
        assert "valid" not in payload
    else:
        assert "--warrant" in result.stderr
        assert result.stdout == ""


@pytest.mark.parametrize("content", [None, "{", "{}", "[]"])
def test_FR_CLI_001_unreadable_warrant_is_a_structured_error(
    tmp_path: Path, content: str | None
) -> None:
    path = tmp_path / "input.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    result = subprocess.run(
        [*ENTRY, "--json", "warrant", "verify", "--warrant", str(path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["code"] == "warrant_unreadable"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("action", ["show", "export"])
def test_FR_CLI_001_warrant_show_export_require_a_file(tmp_path: Path, action: str) -> None:
    result = subprocess.run(
        [*ENTRY, "--json", "warrant", action],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["code"] == "warrant_required"
    assert list(tmp_path.iterdir()) == []


def test_FR_CLI_001_warrant_show_and_export_reflect_the_real_warrant(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "examples/campaign_retention"
    run = AssessmentRunner().run(
        data_sources=(example / "customers.csv",),
        spec=load_spec(example / "question.yaml"),
        output_directory=tmp_path,
    )
    path = run.artifacts["warrant"]

    show = subprocess.run(
        [*ENTRY, "--json", "warrant", "show", "--warrant", str(path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert show.returncode == 0
    payload = json.loads(show.stdout)
    assert payload["warrant_id"] == json.loads(path.read_text())["warrant_id"]
    assert "data" in payload

    export = subprocess.run(
        [*ENTRY, "--json", "warrant", "export", "--warrant", str(path), "--format", "markdown"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert export.returncode == 0
    export_payload = json.loads(export.stdout)
    assert "## " in export_payload["rendered"]


def test_FR_CLI_001_real_warrant_and_tampering_have_distinct_exit_codes(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "examples/campaign_retention"
    run = AssessmentRunner().run(
        data_sources=(example / "customers.csv",),
        spec=load_spec(example / "question.yaml"),
        output_directory=tmp_path,
    )
    path = run.artifacts["warrant"]
    for tampered, expected in [(False, 0), (True, 3)]:
        if tampered:
            record = json.loads(path.read_text())
            record["canonical_json"] += " "
            path.write_text(json.dumps(record))
        for json_mode in [False, True]:
            result = subprocess.run(
                [
                    *ENTRY,
                    *(["--json"] if json_mode else []),
                    "warrant",
                    "verify",
                    "--warrant",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert result.returncode == expected
            if json_mode:
                assert json.loads(result.stdout)["valid"] is (not tampered)
            else:
                assert ("INVALID" if tampered else "valid") in (result.stdout + result.stderr)
                assert ": ok" not in result.stdout
