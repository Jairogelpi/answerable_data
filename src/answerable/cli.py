from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

COMMANDS = ("init", "assess", "frame", "plan", "execute", "inspect", "doctor", "benchmark")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="answerable")
    parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparsers.add_parser(command)
    warrant = subparsers.add_parser("warrant")
    warrant.add_argument("action", choices=("show", "export", "verify"))
    source = subparsers.add_parser("source")
    source.add_argument("action", choices=("add", "test"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = {"status": "ok", "command": args.command}
    if getattr(args, "action", None):
        payload["action"] = args.action
    if args.json_output:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"answerable {args.command}: ok")
    return 0
