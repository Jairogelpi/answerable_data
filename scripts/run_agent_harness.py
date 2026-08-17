"""Run the frozen EMT v1 cases through real agents (Claude, Codex, Gemini).

Claude and Codex shell out to the `claude`/`codex` CLIs already authenticated
on this machine, spending the operator's own subscription rather than a
metered API key. Gemini calls the public API directly (no CLI available),
reading GEMINI_API_KEY from the environment -- never pass it on the command
line, where it would land in shell history and process listings.

Usage:
    export GEMINI_API_KEY=...  # only if "gemini" is in --agents
    python scripts/run_agent_harness.py \\
        --cases benchmarks/releases/emt-v1/cases.jsonl \\
        --output runs/emt-agents \\
        --agents claude,codex,gemini \\
        --repetitions 2

Writes:
    <output>/decisions.jsonl   -- agent_id, repetition, pair_id, action
                                   (the schema scripts/score_mutation_agents.py reads)
    <output>/raw.jsonl         -- one full record per call: prompt, raw response,
                                   model, timestamp, latency, tokens, cost, case hash

Score the result with:
    python scripts/score_mutation_agents.py <output>/decisions.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

_ACTIONS = ("KEEP", "QUALIFY", "RETRACT", "REVERSE")
_ACTION_PATTERN = re.compile(r"\b(" + "|".join(_ACTIONS) + r")\b")
_CALL_TIMEOUT_SECONDS = 180


def _executable(name: str) -> str:
    """Resolve a CLI on PATH, including PATHEXT variants (.cmd) on Windows.

    subprocess.run's CreateProcess does not do PATHEXT resolution itself, so
    a bare "claude" fails to launch on Windows even though the shell finds it.
    """
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"'{name}' not found on PATH")
    return resolved


_JUDGE_SYSTEM_PROMPT = (
    "You are an analytical judge. You are given a question, a prior conclusion, "
    "baseline evidence, and evidence after one change. The evidence given is "
    "complete and final; do not ask for additional data, files, or context. "
    "Decide whether the prior conclusion should be KEPT (unchanged), QUALIFIED "
    "(same direction, weaker), RETRACTED (evidence no longer supports it), or "
    "REVERSED (evidence now points the other way). Answer with exactly one of "
    "those four words and nothing else."
)


class AgentCallResult(NamedTuple):
    action: str | None
    raw_text: str
    model: str | None
    latency_ms: int
    metadata: dict[str, object]


def build_prompt(case: dict[str, object]) -> str:
    actions = ", ".join(_ACTIONS)
    return (
        f"Question: {case['question']}\n"
        f"Previous conclusion: {case['previous_conclusion']}\n"
        f"Baseline evidence: {json.dumps(case['baseline_evidence'], sort_keys=True)}\n"
        f"Mutated evidence: {json.dumps(case['mutated_evidence'], sort_keys=True)}\n\n"
        f"{case['instruction']}\n"
        f"Respond with exactly one word, one of: {actions}. No explanation."
    )


def parse_action(text: str) -> str | None:
    """First allowed action token in the reply, case-insensitive. None if absent."""
    match = _ACTION_PATTERN.search(text.upper())
    return match.group(1) if match else None


def _run_claude(prompt: str, *, model: str, scratch_dir: Path) -> AgentCallResult:
    # This is a pure text-in/text-out judgment call, not an agentic task, so:
    # --system-prompt replaces the default Claude Code persona and its
    # project/global hooks (CLAUDE.md, memory, custom modes) instead of
    # appending to them; --setting-sources "" stops user/project/local
    # settings from loading at all. Without both, the CLI answers in
    # whatever persona is configured on this machine and may refuse the
    # task asking for "the real data" instead of judging the evidence given.
    # cwd=scratch_dir (outside the repo) is a second, independent guard.
    #
    # The prompt travels over stdin, not argv: the resolved executable is
    # claude.CMD (a batch-file shim), and Windows routes argv for .cmd
    # targets through cmd.exe's own quoting, which mangles an argument
    # containing embedded JSON quotes -- the model would see a corrupted
    # prompt and, unsurprisingly, ask for "the real data".
    start = time.perf_counter()
    completed = subprocess.run(
        [
            _executable("claude"),
            "-p",
            "--output-format",
            "json",
            "--model",
            model,
            "--system-prompt",
            _JUDGE_SYSTEM_PROMPT,
            "--setting-sources",
            "",
            "--disallowedTools",
            "*",
        ],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_CALL_TIMEOUT_SECONDS,
        check=False,
        cwd=scratch_dir,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    try:
        payload = json.loads(completed.stdout or "")
    except json.JSONDecodeError:
        return AgentCallResult(
            None, (completed.stdout or "") + (completed.stderr or ""), None, latency_ms, {}
        )
    text = str(payload.get("result", ""))
    model_usage = payload.get("modelUsage") or {}
    resolved_model = next(iter(model_usage), None)
    metadata = {
        "session_id": payload.get("session_id"),
        "total_cost_usd": payload.get("total_cost_usd"),
        "usage": payload.get("usage"),
        "duration_ms": payload.get("duration_ms"),
    }
    return AgentCallResult(parse_action(text), text, resolved_model, latency_ms, metadata)


def _run_codex(prompt: str, *, model: str | None, scratch_dir: Path) -> AgentCallResult:
    # Same stdin-not-argv reasoning as _run_claude: codex.exe is a real
    # executable (no .cmd shim), so argv works, but stdin avoids the shell
    # quoting question entirely and matches what "Reading prompt from
    # stdin..." expects when no PROMPT argument is given.
    # --skip-git-repo-check: scratch_dir is not a git repo and codex refuses
    # to run outside a trusted/git directory otherwise.
    # model is optional: an operator's default in ~/.codex/config.toml is
    # not portable across machines, so leave -m off unless overridden.
    args = [
        _executable("codex"),
        "exec",
        "--json",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
    ]
    if model:
        args += ["-m", model]
    start = time.perf_counter()
    completed = subprocess.run(
        args,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_CALL_TIMEOUT_SECONDS,
        check=False,
        cwd=scratch_dir,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    text = ""
    usage: dict[str, object] = {}
    thread_id = None
    for line in (completed.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
        elif event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                text = str(item.get("text", ""))
        elif event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
    metadata = {"thread_id": thread_id, "usage": usage, "model_requested": model}
    return AgentCallResult(
        parse_action(text), text or (completed.stderr or ""), model, latency_ms, metadata
    )


_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_GEMINI_RETRY_STATUSES = {429, 500, 503}
_GEMINI_RETRY_DELAY_PATTERN = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
# Free-tier gemini-2.5-flash is capped at 5 requests/minute (confirmed from a
# live 429 body: "limit: 5, model: gemini-2.5-flash"). A burst of calls at
# the ~3-4s latency this API otherwise allows blows through that in under a
# minute and then the quota never recovers within a couple of short retries
# -- 76/96 calls failed that way on the first full run. Pacing calls to stay
# under the limit, plus honoring the server's own "retry in Xs" on the 429s
# that still happen, is what makes a full run reliable instead of lucky.
_GEMINI_MIN_INTERVAL_SECONDS = 13.0
_gemini_last_call_at = 0.0


def _run_gemini(prompt: str, *, model: str, scratch_dir: Path) -> AgentCallResult:
    # No official Gemini CLI to shell out to, so this calls the API directly.
    # scratch_dir is unused (there's no cwd/persona to escape from), kept
    # only so this runner has the same signature as the CLI-backed ones.
    global _gemini_last_call_at
    del scratch_dir
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set")
    payload = json.dumps(
        {
            "systemInstruction": {"parts": [{"text": _JUDGE_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": prompt}]}],
        }
    ).encode("utf-8")
    url = _GEMINI_API_URL.format(model=model) + f"?key={api_key}"
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    start = time.perf_counter()
    body = b""
    status = 0
    for attempt in range(5):
        since_last = time.perf_counter() - _gemini_last_call_at
        if since_last < _GEMINI_MIN_INTERVAL_SECONDS:
            time.sleep(_GEMINI_MIN_INTERVAL_SECONDS - since_last)
        _gemini_last_call_at = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=_CALL_TIMEOUT_SECONDS) as response:
                body = response.read()
                status = response.status
            break
        except urllib.error.HTTPError as exc:
            body = exc.read()
            status = exc.code
            if status not in _GEMINI_RETRY_STATUSES or attempt == 4:
                break
            match = _GEMINI_RETRY_DELAY_PATTERN.search(body.decode("utf-8", "replace"))
            time.sleep(float(match.group(1)) + 1.0 if match else 2**attempt)
        except urllib.error.URLError as exc:
            body = str(exc).encode("utf-8")
            status = 0
            break
    latency_ms = int((time.perf_counter() - start) * 1000)
    try:
        payload_response = json.loads(body)
    except json.JSONDecodeError:
        return AgentCallResult(None, body.decode("utf-8", "replace"), None, latency_ms, {})
    if "error" in payload_response:
        return AgentCallResult(
            None, json.dumps(payload_response), None, latency_ms, {"http_status": status}
        )
    try:
        text = payload_response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return AgentCallResult(None, json.dumps(payload_response), model, latency_ms, {})
    metadata = {
        "usage": payload_response.get("usageMetadata"),
        "model_version": payload_response.get("modelVersion"),
        "response_id": payload_response.get("responseId"),
        "http_status": status,
    }
    return AgentCallResult(parse_action(text), text, model, latency_ms, metadata)


AGENT_RUNNERS: dict[str, Callable[[str, str, Path], AgentCallResult]] = {
    "claude": lambda prompt, model, scratch_dir: _run_claude(
        prompt, model=model, scratch_dir=scratch_dir
    ),
    "codex": lambda prompt, model, scratch_dir: _run_codex(
        prompt, model=model, scratch_dir=scratch_dir
    ),
    "gemini": lambda prompt, model, scratch_dir: _run_gemini(
        prompt, model=model, scratch_dir=scratch_dir
    ),
}
_DEFAULT_MODEL: dict[str, str | None] = {
    "claude": "sonnet",
    "codex": None,
    # gemini-2.5-flash's free tier is capped at 20 requests/DAY (confirmed
    # from a live 429 body: quotaId GenerateRequestsPerDayPerProjectPerModel-
    # FreeTier, quotaValue 20) -- one 48-case run alone exhausts it for the
    # rest of the day, and no retry/backoff fixes a daily cap. flash-lite is
    # a separate quota bucket with a workable free-tier daily limit.
    "gemini": "gemini-2.5-flash-lite",
}


def _load_cases(path: Path, limit: int | None) -> list[dict[str, object]]:
    cases = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return cases[:limit] if limit else cases


def _case_hash(case: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(case, sort_keys=True).encode("utf-8")).hexdigest()


def run(
    *,
    cases_path: Path,
    output_dir: Path,
    agent_ids: tuple[str, ...],
    models: dict[str, str],
    repetitions: int,
    limit: int | None,
    scratch_dir: Path,
) -> int:
    cases = _load_cases(cases_path, limit)
    output_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = output_dir / "decisions.jsonl"
    raw_path = output_dir / "raw.jsonl"
    total_calls = len(agent_ids) * repetitions * len(cases)
    done = 0
    with (
        decisions_path.open("a", encoding="utf-8") as decisions_file,
        raw_path.open("a", encoding="utf-8") as raw_file,
    ):
        for agent_id in agent_ids:
            runner = AGENT_RUNNERS[agent_id]
            model = models[agent_id]
            for repetition in (1, 2)[:repetitions]:
                for case in cases:
                    prompt = build_prompt(case)
                    result = runner(prompt, model, scratch_dir)
                    done += 1
                    print(
                        f"[{done}/{total_calls}] {agent_id} rep{repetition} "
                        f"{case['pair_id']} -> {result.action or 'UNPARSEABLE'} "
                        f"({result.latency_ms}ms)"
                    )
                    timestamp = datetime.now(UTC).isoformat()
                    raw_file.write(
                        json.dumps(
                            {
                                "agent_id": agent_id,
                                "repetition": repetition,
                                "pair_id": case["pair_id"],
                                "case_hash": _case_hash(case),
                                "model": result.model or model,
                                "model_requested": model,
                                "timestamp": timestamp,
                                "prompt": prompt,
                                "raw_response": result.raw_text,
                                "parsed_action": result.action,
                                "latency_ms": result.latency_ms,
                                **result.metadata,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    raw_file.flush()
                    if result.action is not None:
                        decisions_file.write(
                            json.dumps(
                                {
                                    "agent_id": agent_id,
                                    "repetition": repetition,
                                    "pair_id": case["pair_id"],
                                    "action": result.action,
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        decisions_file.flush()
    print(f"decisions: {decisions_path}")
    print(f"raw log:   {raw_path}")
    return 0


def _selfcheck() -> int:
    """Pure-function checks only: no subprocess, no network, runs in CI."""
    case = {
        "pair_id": "emt-causal-01-evidence_invalidation",
        "question": "Did exposure increase 90-day retention?",
        "previous_conclusion": "Exposure increased retention.",
        "baseline_evidence": {"rows": 24},
        "mutated_evidence": {"rows": 24},
        "instruction": "Choose one action.",
    }
    prompt = build_prompt(case)
    assert "RETRACT" in prompt and "REVERSE" in prompt
    assert case["question"] in prompt

    assert parse_action("RETRACT") == "RETRACT"
    assert parse_action("The answer is retract.") == "RETRACT"
    assert parse_action("I think we should REVERSE this.") == "REVERSE"
    assert parse_action("no valid token here") is None
    assert parse_action("RETRACTOR") is None  # word-boundary match, not substring

    hash_a = _case_hash(case)
    hash_b = _case_hash(dict(case))
    assert hash_a == hash_b
    assert len(hash_a) == 64

    print("selfcheck: ok")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen EMT cases through real CLI agents.")
    parser.add_argument(
        "--cases", type=Path, default=Path("benchmarks/releases/emt-v1/cases.jsonl")
    )
    parser.add_argument("--output", type=Path, default=Path("runs/emt-agents"))
    parser.add_argument("--agents", default="claude,codex")
    parser.add_argument("--repetitions", type=int, default=2, choices=(1, 2))
    parser.add_argument("--limit", type=int, default=None, help="Use only the first N cases.")
    parser.add_argument("--claude-model", default=_DEFAULT_MODEL["claude"])
    parser.add_argument("--codex-model", default=_DEFAULT_MODEL["codex"])
    parser.add_argument("--gemini-model", default=_DEFAULT_MODEL["gemini"])
    parser.add_argument("--selfcheck", action="store_true", help="Run offline checks and exit.")
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "answerable-emt-scratch",
        help="Working directory agents run from, kept outside this repo so a "
        "coding agent doesn't explore repo files instead of judging the prompt.",
    )
    args = parser.parse_args()

    if args.selfcheck:
        return _selfcheck()

    agent_ids = tuple(item.strip() for item in args.agents.split(",") if item.strip())
    unknown = [item for item in agent_ids if item not in AGENT_RUNNERS]
    if unknown:
        raise SystemExit(f"unknown agent(s): {unknown}. Choose from {sorted(AGENT_RUNNERS)}.")
    models = {
        "claude": args.claude_model,
        "codex": args.codex_model,
        "gemini": args.gemini_model,
    }
    return run(
        cases_path=args.cases,
        output_dir=args.output,
        agent_ids=agent_ids,
        models=models,
        repetitions=args.repetitions,
        limit=args.limit,
        scratch_dir=args.scratch_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
