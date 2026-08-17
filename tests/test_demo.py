from __future__ import annotations

from pathlib import Path

import pytest

from answerable.demo import CASES, run_demo


@pytest.mark.parametrize(
    ("case_name", "expected_signal"),
    [
        ("causal", "positivity_violation"),
        ("grain", "duplicate_entities"),
        ("maturity", "immature_cohort"),
    ],
)
def test_golden_demo_surfaces_expected_blocker(
    tmp_path: Path, case_name: str, expected_signal: str
) -> None:
    case, run = run_demo(case_name, tmp_path / case_name)

    assert case is CASES[case_name]
    assert expected_signal in {item.finding_id for item in run.blockers}
    assert run.artifacts["warrant"].is_file()
    assert run.artifacts["warrant_markdown"].is_file()


def test_demo_is_deterministic_across_output_directories(tmp_path: Path) -> None:
    _, first = run_demo("causal", tmp_path / "first")
    _, second = run_demo("causal", tmp_path / "second")

    assert first.assessment_id == second.assessment_id
    assert first.verdict == second.verdict
    assert first.allowed_claims == second.allowed_claims
    assert first.forbidden_claims == second.forbidden_claims
