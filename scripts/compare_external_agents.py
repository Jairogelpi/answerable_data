"""Paired text-agent experiment with an actual, mediated Answerable tool call.

The same pinned model/command receives the same evidence in both arms. Only
tool availability changes. No raw rows, oracle labels or repo paths are sent.
The command reads a prompt from stdin and returns text on stdout; it must be
configured as a text-only model adapter, without ambient tools or memory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from evaluate_external import digest, materialize, metrics

from answerable.interfaces.mcp_handlers import assess_answerability


def build_context(folder: Path) -> dict[str, object]:
    contract = json.loads((folder / "question.json").read_text())
    with (folder / "data.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    groups = sorted({r["group"] for r in rows})
    return {
        "claim": contract["claims"][0],
        "population": contract["population"],
        "outcome": contract["outcome"],
        "analysis_type": contract["analysis_type"],
        "design": contract["causal"],
        "time": contract["time"],
        "row_count": len(rows),
        "unique_entities": len({r["entity"] for r in rows}),
        "group_counts": dict(Counter(r["group"] for r in rows)),
        "group_means": {
            g: mean(float(r["value"]) for r in rows if r["group"] == g) for g in groups
        },
    }


def parse_decision(text: str) -> bool | None:
    matches = re.findall(r"^DECISION: (ALLOW|BLOCK)$", text.strip(), flags=re.MULTILINE)
    if len(matches) != 1 or text.strip().splitlines()[-1] != f"DECISION: {matches[0]}":
        return None
    return matches[0] == "ALLOW"


def run_case(
    command: list[str], model: str, folder: Path, arm: str, timeout: float = 180
) -> dict[str, object]:
    context = build_context(folder)
    prompt = (
        "Assess whether the exact claim is supported by the provided evidence. "
        "Descriptive sample statements do not imply population inference or causality. "
        "Do not use external files, tools or memory. Explain briefly, then end with exactly "
        "DECISION: ALLOW or DECISION: BLOCK on its own line.\n"
        + json.dumps(context, sort_keys=True)
        + "\n"
    )
    if arm == "tool":
        prompt += (
            "A deterministic assessment tool is available. To call it, respond with exactly "
            "CALL_ANSWERABLE. You will receive its real result, then make your own decision.\n"
        )
    else:
        prompt += "No assessment tool is available.\n"
    transcript = []
    tool_calls = []
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="answerable-agent-") as scratch:
        for turn in range(2):
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    capture_output=True,
                    cwd=scratch,
                    timeout=timeout,
                    check=False,
                )
                transcript.append(
                    {
                        "prompt": prompt,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "returncode": completed.returncode,
                    }
                )
                if completed.returncode:
                    raise RuntimeError(f"adapter exited {completed.returncode}")
                response = completed.stdout.strip()
                if response == "CALL_ANSWERABLE" and arm == "tool" and turn == 0:
                    result = assess_answerability(
                        {
                            "data": str(folder / "data.csv"),
                            "question": str(folder / "question.json"),
                            "output": str(folder / "tool-assessment"),
                        }
                    )
                    # Strip filesystem paths and identifiers; preserve substantive outputs.
                    public = {
                        key: result[key]
                        for key in ("verdict", "blockers", "allowed_claims", "forbidden_claims")
                    }
                    tool_calls.append({"tool": "assess_answerability", "result": public})
                    prompt += (
                        "\nAssistant: CALL_ANSWERABLE\nTool: "
                        + json.dumps(public)
                        + "\nThe tool call is complete. Return your final decision now.\n"
                    )
                    continue
                decision = parse_decision(response)
                if decision is None:
                    raise ValueError("missing or ambiguous final decision")
                return {
                    "allowed": decision,
                    "model": model,
                    "transcript": transcript,
                    "tool_calls": tool_calls,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                }
            except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError) as error:
                return {
                    "allowed": None,
                    "model": model,
                    "error": str(error),
                    "transcript": transcript,
                    "tool_calls": tool_calls,
                }
    raise AssertionError("unreachable")


def paired_metrics(records: list[dict[str, object]]) -> dict[str, object]:
    arms = {arm: metrics([r for r in records if r["arm"] == arm]) for arm in ("alone", "tool")}
    arms["tool"]["tool_call_count"] = sum(len(r.get("tool_calls", [])) for r in records)
    by_pair = {}
    for row in records:
        by_pair.setdefault((row["case_id"], row["repetition"]), {})[row["arm"]] = row
    comparable = improved = regressed = 0
    for pair in by_pair.values():
        if len(pair) != 2 or any(row["allowed"] is None for row in pair.values()):
            continue
        comparable += 1
        before = pair["alone"]["allowed"] == pair["alone"]["expected_allow"]
        after = pair["tool"]["allowed"] == pair["tool"]["expected_allow"]
        improved += not before and after
        regressed += before and not after
    return {
        "arms": arms,
        "complete_pairs": comparable,
        "improved": improved,
        "regressed": regressed,
        "accuracy_delta": (improved - regressed) / comparable if comparable else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command-json", help="JSON argv array of a text-only model adapter")
    parser.add_argument("--model", help="Exact provider model identifier (required for a real run)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("repetitions must be positive")
    args.output = args.output.resolve()
    if (args.output / "report.json").exists():
        parser.error("output already contains a report; use a new run directory")
    cases = materialize(args.output)
    command = json.loads(args.command_json) if args.command_json else []
    if command and (not isinstance(command, list) or not all(isinstance(x, str) for x in command)):
        parser.error("command-json must be an argv array")
    available = bool(command and shutil.which(command[0]) and args.model)
    manifest = {
        "protocol": "paired-external-v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "model": args.model,
        "command": command,
        "repetitions": args.repetitions,
        "seed": args.seed,
        "case_count": len(cases),
        "cases": cases,
        "adapter_requirement": "text-only, no ambient tools or memory",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if not available:
        report = {
            "status": "not_run",
            "reason": "No available text-model command and pinned model.",
            "detected_cli": {name: shutil.which(name) for name in ("claude", "codex")},
            "expected_decisions": len(cases) * args.repetitions * 2,
            "actual_decisions": 0,
            "metrics": None,
            "manifest_sha256": digest(args.output / "manifest.json"),
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2
    records = []
    order = [(case, repetition) for case in cases for repetition in range(args.repetitions)]
    random.Random(args.seed).shuffle(order)
    with (args.output / "raw.jsonl").open("w") as log:
        for index, (case, repetition) in enumerate(order):
            # Counterbalance condition order; each invocation uses a fresh process/directory.
            for arm in ("alone", "tool") if index % 2 == 0 else ("tool", "alone"):
                folder = args.output / "cases" / case["case_id"]
                record = {
                    "case_id": case["case_id"],
                    "repetition": repetition,
                    "arm": arm,
                    "expected_allow": case["expected_allow"],
                    "data_sha256": case["data_sha256"],
                    "question_sha256": case["question_sha256"],
                    **run_case(command, args.model, folder, arm),
                }
                records.append(record)
                log.write(json.dumps(record) + "\n")
                log.flush()
    report = {
        "status": "completed" if all(r["allowed"] is not None for r in records) else "incomplete",
        "metrics": paired_metrics(records),
        "actual_decisions": sum(r["allowed"] is not None for r in records),
        "manifest_sha256": digest(args.output / "manifest.json"),
        "raw_sha256": hashlib.sha256((args.output / "raw.jsonl").read_bytes()).hexdigest(),
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(report["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
