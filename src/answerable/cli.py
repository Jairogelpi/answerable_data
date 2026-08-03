from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from answerable.domain.models import Verdict

COMMANDS = ("init", "frame", "plan", "execute", "inspect", "doctor", "benchmark")
_CLEAN_VERDICTS = frozenset({Verdict.ANSWERABLE, Verdict.ANSWERABLE_WITH_ASSUMPTIONS})
EXIT_BLOCKED = 2
EXIT_INVALID_WARRANT = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="answerable")
    parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparsers.add_parser(command)
    assess = subparsers.add_parser("assess")
    assess.add_argument("--data", action="append", type=Path, default=None, required=True)
    assess.add_argument("--question", type=Path, required=True)
    assess.add_argument("--output", type=Path, required=True)
    assess.add_argument("--format", choices=("json", "markdown", "both"), default="both")
    warrant = subparsers.add_parser("warrant")
    warrant.add_argument("action", choices=("show", "export", "verify"))
    warrant.add_argument("--warrant", type=Path, default=None)
    source = subparsers.add_parser("source")
    source.add_argument("action", choices=("add", "test"))
    return parser


def _assess(args: argparse.Namespace, *, json_output: bool) -> tuple[int, dict[str, object]]:
    from answerable.application.assessment_runner import AssessmentRunner
    from answerable.application.spec_loader import load_spec

    run = AssessmentRunner().run(
        data_sources=tuple(args.data),
        spec=load_spec(args.question),
        output_directory=args.output,
    )
    if args.format == "json":
        run.artifacts.pop("warrant_markdown").unlink()
    elif args.format == "markdown":
        for name in tuple(run.artifacts):
            if name != "warrant_markdown":
                run.artifacts.pop(name).unlink()
    artifacts = {name: str(path) for name, path in sorted(run.artifacts.items())}
    if not json_output:
        print(f"Assessment: {run.assessment_id}")
        print(f"Verdict: {run.verdict.value}")
        print(f"Blockers: {len(run.blockers)}")
        print(f"Allowed claims: {len(run.allowed_claims)}")
        print(f"Forbidden claims: {len(run.forbidden_claims)}")
        for name, path in artifacts.items():
            print(f"{name}: {path}")
    payload: dict[str, object] = {
        "assessment_id": run.assessment_id,
        "verdict": run.verdict.value,
        "blockers": [item.finding_id for item in run.blockers],
        "allowed_claims": list(run.allowed_claims),
        "forbidden_claims": list(run.forbidden_claims),
        "artifacts": artifacts,
    }
    return (0 if run.verdict in _CLEAN_VERDICTS else EXIT_BLOCKED), payload


def _verify(path: Path) -> tuple[int, dict[str, object]]:
    from answerable.application.assessment_runner import load_warrant
    from answerable.public import verify_warrant

    valid = verify_warrant(load_warrant(path))
    return (0 if valid else EXIT_INVALID_WARRANT), {"warrant": str(path), "valid": valid}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "assess":
        code, payload = _assess(args, json_output=args.json_output)
    elif args.command == "warrant" and args.action == "verify" and args.warrant is not None:
        code, payload = _verify(args.warrant)
    else:
        code, payload = 0, {"status": "ok"}
    payload["command"] = args.command
    if getattr(args, "action", None):
        payload["action"] = args.action
    if args.json_output:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    elif args.command != "assess":
        print(f"answerable {args.command}: ok")
    return code
