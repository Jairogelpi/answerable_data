from __future__ import annotations

import json
from pathlib import Path

from answerable.benchmark_release import RELEASE_ID, freeze_benchmark, verify_release


def test_freeze_writes_every_artifact_and_verifies(tmp_path: Path) -> None:
    release = freeze_benchmark(tmp_path)

    assert release.release_id == RELEASE_ID
    assert release.case_count == 112
    assert release.scenario_count == 28
    assert len(release.release_hash) == 64
    for name in ("manifest.json", "cases.jsonl", "oracle.json", "protocol.md", "SHA256SUMS"):
        assert (tmp_path / name).is_file()
    assert verify_release(tmp_path)


def test_release_hash_is_stable_across_directories(tmp_path: Path) -> None:
    first = freeze_benchmark(tmp_path / "a")
    second = freeze_benchmark(tmp_path / "b")

    assert first.release_hash == second.release_hash
    assert first.checksums == second.checksums


def test_editing_a_frozen_case_breaks_verification(tmp_path: Path) -> None:
    freeze_benchmark(tmp_path)
    cases = tmp_path / "cases.jsonl"
    original = cases.read_text(encoding="utf-8")
    edited = original.replace("irrelevant_noise", "outcome_reversal", 1)
    assert edited != original
    cases.write_text(edited, encoding="utf-8", newline="\n")

    assert not verify_release(tmp_path)


def test_cases_carry_no_answers_and_oracle_covers_every_case(tmp_path: Path) -> None:
    freeze_benchmark(tmp_path)
    cases = [
        json.loads(line)
        for line in (tmp_path / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    oracle = json.loads((tmp_path / "oracle.json").read_text(encoding="utf-8"))

    # A blind run gets cases.jsonl only, so it must not leak expected actions.
    assert all("expected_action" not in case for case in cases)
    assert set(oracle["expected_action"]) == {case["pair_id"] for case in cases}
    assert set(oracle["expected_blocker"]) == {case["failure_class"] for case in cases}
