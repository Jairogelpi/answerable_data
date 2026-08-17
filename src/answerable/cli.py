from __future__ import annotations

import argparse
import json
import platform
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import cast

from answerable.application.models import AssessmentRun
from answerable.domain.models import Verdict

COMMANDS = ("init", "frame", "plan", "execute", "inspect")
_CLEAN_VERDICTS = frozenset({Verdict.ANSWERABLE, Verdict.ANSWERABLE_WITH_ASSUMPTIONS})
EXIT_BLOCKED = 2
EXIT_INVALID_WARRANT = 3
EXIT_BENCHMARK_FAILED = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="answerable",
        description="Test whether evidence actually supports an analytical conclusion.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparsers.add_parser(command)

    subparsers.add_parser("doctor", help="Check that the local Answerable runtime is ready.")

    demo = subparsers.add_parser("demo", help="Run a built-in adversarial analytical case.")
    demo.add_argument("case", nargs="?", choices=("causal", "grain", "maturity"), default="causal")
    demo.add_argument("--output", type=Path, default=None)

    benchmark = subparsers.add_parser(
        "benchmark", help="Execute release-gating analytical validity benchmarks."
    )
    benchmark.add_argument("suite", nargs="?", choices=("mutations",), default="mutations")
    benchmark.add_argument("--output", type=Path, default=Path("answerable-benchmark/mutations"))
    benchmark.add_argument(
        "--freeze",
        action="store_true",
        help="Write the frozen, hash-addressed benchmark release instead of running it.",
    )

    assess = subparsers.add_parser("assess", help="Run data and a question to an Evidence Warrant.")
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


def _print_run(run: AssessmentRun) -> None:
    print(f"Assessment: {run.assessment_id}")
    print(f"Verdict: {run.verdict.value}")
    print(f"Blockers: {len(run.blockers)}")
    if run.blockers:
        for blocker in run.blockers:
            print(f"  x {blocker.finding_id}: {blocker.message}")
    print("Supported claims:")
    if run.allowed_claims:
        for claim in run.allowed_claims:
            print(f"  + {claim}")
    else:
        print("  (none)")
    print("Unsupported claims:")
    if run.forbidden_claims:
        for claim in run.forbidden_claims:
            print(f"  - {claim}")
    else:
        print("  (none)")
    print("Artifacts:")
    for name, path in sorted(run.artifacts.items()):
        print(f"  {name}: {path}")


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
        _print_run(run)
    payload: dict[str, object] = {
        "assessment_id": run.assessment_id,
        "verdict": run.verdict.value,
        "blockers": [item.finding_id for item in run.blockers],
        "allowed_claims": list(run.allowed_claims),
        "forbidden_claims": list(run.forbidden_claims),
        "artifacts": artifacts,
    }
    return (0 if run.verdict in _CLEAN_VERDICTS else EXIT_BLOCKED), payload


def _demo(args: argparse.Namespace, *, json_output: bool) -> tuple[int, dict[str, object]]:
    from answerable.demo import run_demo

    output = args.output or Path("answerable-demo") / args.case
    case, run = run_demo(args.case, output)
    if not json_output:
        print("Answerable demo")
        print(f"Case: {case.title}")
        print(f"Question: {case.question}")
        print(f"Trap: {case.trap}")
        print()
        _print_run(run)
        print()
        print(f"Expected signal: {case.expected_signal}")
        print(f"Open the human-readable warrant: {run.artifacts['warrant_markdown']}")
    payload: dict[str, object] = {
        "case": case.name,
        "title": case.title,
        "question": case.question,
        "trap": case.trap,
        "expected_signal": case.expected_signal,
        "assessment_id": run.assessment_id,
        "verdict": run.verdict.value,
        "blockers": [item.finding_id for item in run.blockers],
        "allowed_claims": list(run.allowed_claims),
        "forbidden_claims": list(run.forbidden_claims),
        "artifacts": {name: str(path) for name, path in sorted(run.artifacts.items())},
    }
    return 0, payload


def _freeze(args: argparse.Namespace, *, json_output: bool) -> tuple[int, dict[str, object]]:
    from answerable.benchmark_release import freeze_benchmark

    release = freeze_benchmark(args.output)
    payload: dict[str, object] = {
        "release_id": release.release_id,
        "case_count": release.case_count,
        "scenario_count": release.scenario_count,
        "release_hash": release.release_hash,
        "checksums": release.checksums,
        "directory": str(args.output),
    }
    if not json_output:
        print(f"AnswerableBench {release.release_id} — frozen")
        print(f"Scenarios: {release.scenario_count}")
        print(f"Cases: {release.case_count}")
        print(f"Release hash: {release.release_hash}")
        print(f"Directory: {args.output}")
    return 0, payload


def _benchmark(args: argparse.Namespace, *, json_output: bool) -> tuple[int, dict[str, object]]:
    from answerable.mutation_benchmark import report_to_dict, run_mutation_benchmark

    if args.freeze:
        return _freeze(args, json_output=json_output)
    report = run_mutation_benchmark(args.output)
    payload = report_to_dict(report)
    payload["suite"] = args.suite
    payload["report"] = str(args.output / "mutation_report.json")
    if not json_output:
        print("AnswerableBench — Epistemic Mutation Testing")
        print(f"Pairs: {report.total_pairs}")
        print(f"Action accuracy: {report.action_accuracy:.1%}")
        print(f"Unsafe KEEP rate: {report.unsafe_keep_rate:.1%}")
        print(f"Overreaction rate: {report.overreaction_rate:.1%}")
        print(f"QUALIFY recall: {report.qualify_recall:.1%}")
        print(f"RETRACT recall: {report.retract_recall:.1%}")
        print(f"REVERSE recall: {report.reverse_recall:.1%}")
        for family, accuracy in sorted(report.family_accuracy.items()):
            print(f"  {family}: {accuracy:.1%}")
        for failure_class, accuracy in sorted(report.class_accuracy.items()):
            print(f"  class {failure_class}: {accuracy:.1%}")
        print(f"Reproducibility: {report.reproducibility_hash}")
        print(f"Release gate: {'PASS' if report.release_pass else 'FAIL'}")
        print(f"Report: {args.output / 'mutation_report.json'}")
    return (0 if report.release_pass else EXIT_BENCHMARK_FAILED), payload


def _doctor() -> tuple[int, dict[str, object]]:
    checks: dict[str, str] = {}
    for module in ("duckdb", "sqlglot", "yaml"):
        try:
            __import__(module)
        except ImportError as exc:
            checks[module] = f"missing: {exc}"
        else:
            checks[module] = "ok"
    ready = all(value == "ok" for value in checks.values())
    payload: dict[str, object] = {
        "status": "ready" if ready else "not_ready",
        "version": version("answerable-data"),
        "python": platform.python_version(),
        "dependencies": checks,
        "demos": ["causal", "grain", "maturity"],
    }
    return (0 if ready else 1), payload


def _verify(path: Path) -> tuple[int, dict[str, object]]:
    from answerable.application.assessment_runner import load_warrant
    from answerable.public import verify_warrant

    valid = verify_warrant(load_warrant(path))
    return (0 if valid else EXIT_INVALID_WARRANT), {"warrant": str(path), "valid": valid}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "assess":
        code, payload = _assess(args, json_output=args.json_output)
    elif args.command == "demo":
        code, payload = _demo(args, json_output=args.json_output)
    elif args.command == "benchmark":
        code, payload = _benchmark(args, json_output=args.json_output)
    elif args.command == "doctor":
        code, payload = _doctor()
    elif args.command == "warrant" and args.action == "verify" and args.warrant is not None:
        code, payload = _verify(args.warrant)
    else:
        code, payload = 0, {"status": "ok"}
    payload["command"] = args.command
    if getattr(args, "action", None):
        payload["action"] = args.action
    if args.json_output:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    elif args.command == "doctor":
        print(f"Answerable {payload['version']}")
        print(f"Python {payload['python']}")
        dependencies = cast(dict[str, str], payload["dependencies"])
        for dependency, status in dependencies.items():
            marker = "+" if status == "ok" else "x"
            print(f"{marker} {dependency}: {status}")
        print(f"Status: {payload['status']}")
    elif args.command not in {"assess", "demo", "benchmark"}:
        print(f"answerable {args.command}: ok")
    return code
