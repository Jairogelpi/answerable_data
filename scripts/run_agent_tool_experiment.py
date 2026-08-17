"""Does giving Claude/Codex the `answerable` tool fix the RETRACT gap?

The blind-judgment EMT runs (run_agent_harness.py) show both models score
0-1/8 RETRACT on five of seven failure classes when asked to judge a text
summary of the evidence with no tools. That measures the model's own
judgment. It says nothing about whether an agent with real shell access to
`answerable assess` would defer to it and get these right instead --
that's a different experiment, and this is it.

Each case gets real files (materialize_case), not a text summary: an actual
customers.csv and question.yaml the agent can hand to `answerable assess`
itself. The prompt tells it the tool exists and that a blocked verdict
means the causal claim must not be made -- the same instruction the
README's CLAUDE.md/AGENTS.md snippet gives. Scored the same way as the
blind runs: one action token, against the same oracle.

Scoped to the evidence_invalidation family only (28 cases: 4 per failure
class x 7 classes) -- that's the family the blind runs show is broken, and
an agentic call costs much more time than a blind judgment call (real
subprocess execution, real file I/O, real tool-use turns), so running the
other three families here would not change the answer to the question this
experiment asks and would multiply the cost by 4x for no signal.

Usage:
    python scripts/run_agent_tool_experiment.py --agents claude,codex \\
        --output runs/emt-v2-tool-experiment
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from answerable.mutation_benchmark import (
    MutationFamily,
    benchmark_scenarios,
    blind_question,
    expected_blocker,
    materialize_case,
)

_ACTIONS = ("KEEP", "QUALIFY", "RETRACT", "REVERSE")
_ACTION_PATTERN = re.compile(r"\bACTION:\s*(" + "|".join(_ACTIONS) + r")\b", re.IGNORECASE)
_FALLBACK_PATTERN = re.compile(r"\b(" + "|".join(_ACTIONS) + r")\b")
_CALL_TIMEOUT_SECONDS = 240

_PROMPT_TEMPLATE = """You are deciding whether an analytical claim is still supported.

Question: {question}
Previous conclusion: {previous_conclusion}

Files in this directory: customers.csv, question.yaml -- the real data and
question contract for this analysis (not a summary).

The `answerable` CLI is installed and on PATH. You may run it, e.g.:
    answerable assess --data customers.csv --question question.yaml --output out
A verdict other than ANSWERABLE or ANSWERABLE_WITH_ASSUMPTIONS means the
causal claim is blocked; treat that as authoritative and do not make the
causal claim if so. You are not required to use the tool, but you have real
shell access to it in this directory.

Decide exactly one action for how the previous conclusion should change:
KEEP (unchanged), QUALIFY (same direction, weaker), RETRACT (evidence no
longer supports it), or REVERSE (evidence now points the other way).

End your response with exactly one line in this exact format:
ACTION: <token>
"""


def _executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"'{name}' not found on PATH")
    return resolved


def parse_action(text: str) -> str | None:
    match = _ACTION_PATTERN.search(text)
    if match:
        return match.group(1).upper()
    match = _FALLBACK_PATTERN.search(text.upper())
    return match.group(1) if match else None


def _run_claude(prompt: str, *, model: str, case_dir: Path) -> tuple[str | None, str]:
    completed = subprocess.run(
        [
            _executable("claude"),
            "-p",
            "--output-format",
            "json",
            "--model",
            model,
            "--system-prompt",
            "You are a careful analyst with shell access. Follow the response format exactly.",
            "--setting-sources",
            "",
            "--allowedTools",
            "Bash(answerable *)",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=_CALL_TIMEOUT_SECONDS,
        check=False,
        cwd=case_dir,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, completed.stdout + completed.stderr
    text = str(payload.get("result", ""))
    return parse_action(text), text


def _run_codex(prompt: str, *, model: str | None, case_dir: Path) -> tuple[str | None, str]:
    args = [
        _executable("codex"),
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
    ]
    if model:
        args += ["-m", model]
    completed = subprocess.run(
        args,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=_CALL_TIMEOUT_SECONDS,
        check=False,
        cwd=case_dir,
    )
    text = ""
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                text = str(item.get("text", ""))
    return parse_action(text), text or completed.stderr


_RUNNERS = {"claude": _run_claude, "codex": _run_codex}
_DEFAULT_MODEL = {"claude": "sonnet", "codex": None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", default="claude,codex")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N scenarios.")
    args = parser.parse_args()

    agent_ids = tuple(item.strip() for item in args.agents.split(",") if item.strip())
    scenarios = list(benchmark_scenarios())  # 4 per failure class, 7 classes = 28
    if args.limit:
        scenarios = scenarios[: args.limit]

    args.output.mkdir(parents=True, exist_ok=True)
    decisions_path = args.output / "decisions.jsonl"
    raw_path = args.output / "raw.jsonl"
    total = len(agent_ids) * len(scenarios)
    done = 0
    with (
        decisions_path.open("a", encoding="utf-8") as decisions_file,
        raw_path.open("a", encoding="utf-8") as raw_file,
    ):
        for agent_id in agent_ids:
            runner = _RUNNERS[agent_id]
            model = _DEFAULT_MODEL[agent_id]
            for scenario in scenarios:
                case_dir = args.output / "_cases" / scenario.scenario_id / agent_id
                materialize_case(case_dir, scenario, MutationFamily.EVIDENCE_INVALIDATION)
                question, previous = blind_question(scenario.failure_class)
                prompt = _PROMPT_TEMPLATE.format(question=question, previous_conclusion=previous)
                start = time.perf_counter()
                action, text = runner(prompt, model=model, case_dir=case_dir)  # type: ignore[operator]
                latency_ms = int((time.perf_counter() - start) * 1000)
                done += 1
                pair_id = f"emt-{scenario.scenario_id}-evidence_invalidation"
                print(
                    f"[{done}/{total}] {agent_id} {pair_id} -> "
                    f"{action or 'UNPARSEABLE'} ({latency_ms}ms)"
                )
                raw_file.write(
                    json.dumps(
                        {
                            "agent_id": agent_id,
                            "pair_id": pair_id,
                            "failure_class": scenario.failure_class.value,
                            "expected_blocker": expected_blocker(scenario.failure_class),
                            "response_text": text,
                            "parsed_action": action,
                            "latency_ms": latency_ms,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                raw_file.flush()
                if action is not None:
                    decisions_file.write(
                        json.dumps(
                            {
                                "agent_id": agent_id,
                                "pair_id": pair_id,
                                "failure_class": scenario.failure_class.value,
                                "action": action,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    decisions_file.flush()
    print(f"decisions: {decisions_path}")
    print(f"raw log:   {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
