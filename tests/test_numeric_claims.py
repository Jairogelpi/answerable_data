"""INV-001/002: submitted prose is not evidence of its own truth."""

from dataclasses import replace
from pathlib import Path

import pytest

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.models import ClaimCandidate
from answerable.application.spec_loader import load_spec
from answerable.domain.models import AnalysisType, Verdict
from answerable.evidence.claims import ClaimClass
from tests.e2e.test_runner_edge_cases import _case


@pytest.mark.parametrize(
    "text",
    [
        "Among recorded days, mean rentals were 99999 on working days and 1 on non-working days.",
        "Observed group means were 99999 and 1.",
        "Exposure improved retention.",
    ],
)
def test_INV_002_unverified_text_is_never_supported(tmp_path: Path, text: str) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    spec = load_spec(root / "question.json")
    spec = replace(
        spec,
        contract=replace(spec.contract, analysis_type=AnalysisType.DESCRIPTIVE),
        claims=(ClaimCandidate(text, ClaimClass.DESCRIPTIVE),),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert text not in run.allowed_claims
    assert text in run.forbidden_claims


def test_INV_001_exact_means_preserve_valid_claims_and_reject_mutations(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    spec = load_spec(root / "question.json")
    good = (
        'Observed means of "retained_90d" by "campaign_exposed" among supplied records '
        '(six decimals): "false"=0.500000 (n=4); "true"=0.750000 (n=4).'
    )
    bad = [
        good.replace("0.750000", "99999.000000"),
        good.replace('"false"=0.500000', '"false"=0.750000').replace(
            '"true"=0.750000', '"true"=0.500000'
        ),
        good.replace("(n=4)", "(n=5)"),
        good + " This proves causation.",
        good.replace("retained_90d", "revenue"),
        good.replace("0.750000", "0.750001"),
    ]
    spec = replace(
        spec,
        contract=replace(spec.contract, analysis_type=AnalysisType.DESCRIPTIVE),
        claims=tuple(ClaimCandidate(t, ClaimClass.DESCRIPTIVE) for t in [good, *bad]),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert run.allowed_claims == (good,)
    assert run.forbidden_claims == tuple(bad)
    assert run.warrant.data["allowed_claims"] == [good]
    assert run.observations["computed_mean_claim"] == good
    assert run.observations["claim_validation"][0]["status"] == "supported"
    import json

    graph = json.loads((root / "out/evidence_graph.json").read_text())
    assert [n["payload"]["text"] for n in graph["nodes"] if n["type"] == "allowed_claim"] == [good]


@pytest.mark.parametrize("value", ["", "oops", "NaN", "inf", "-inf"])
def test_INV_002_invalid_outcome_cannot_certify_a_mean(tmp_path: Path, value: str) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    source = root / "customers.csv"
    lines = source.read_text().splitlines()
    lines[1] = lines[1].rsplit(",", 1)[0] + "," + value
    source.write_text("\n".join(lines) + "\n")
    run = AssessmentRunner().run(
        data_sources=(source,),
        spec=load_spec(root / "question.json"),
        output_directory=root / "out",
    )
    assert not run.allowed_claims
    assert run.verdict is Verdict.DATA_INTEGRITY_FAILURE
    assert "invalid_outcome" in {b.finding_id for b in run.blockers}


def test_INV_001_additional_sources_are_not_silently_ignored(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    with pytest.raises(ValueError, match="exactly one data source"):
        AssessmentRunner().run(
            data_sources=(root / "customers.csv", root / "customers.csv"),
            spec=load_spec(root / "question.json"),
            output_directory=root / "out",
        )


def test_INV_001_rounding_and_integrity_are_independent(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    source = root / "customers.csv"
    lines = source.read_text().splitlines()
    lines[1:] = [line.rsplit(",", 1)[0] + ",1.2345674" for line in lines[1:]]
    source.write_text("\n".join(lines) + "\n")
    spec = load_spec(root / "question.json")
    good = (
        'Observed means of "retained_90d" by "campaign_exposed" among supplied records '
        '(six decimals): "false"=1.234567 (n=4); "true"=1.234567 (n=4).'
    )
    spec = replace(
        spec,
        contract=replace(spec.contract, analysis_type=AnalysisType.DESCRIPTIVE),
        claims=(ClaimCandidate(good, ClaimClass.DESCRIPTIVE),),
    )
    run = AssessmentRunner().run(data_sources=(source,), spec=spec, output_directory=root / "out")
    assert run.allowed_claims == (good,)
    source.write_text("\n".join([*lines, lines[1]]) + "\n")
    duplicate = good.replace('"true"=1.234567 (n=4)', '"true"=1.234567 (n=5)')
    spec = replace(spec, claims=(ClaimCandidate(duplicate, ClaimClass.DESCRIPTIVE),))
    run = AssessmentRunner().run(data_sources=(source,), spec=spec, output_directory=root / "dup")
    assert run.observations["computed_mean_claim"] == duplicate
    assert run.verdict is Verdict.DATA_INTEGRITY_FAILURE
    assert run.allowed_claims == ()


def test_INV_002_null_group_blocks_even_matching_arithmetic(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    source = root / "customers.csv"
    source.write_text(source.read_text().replace(",true,", ",,", 1))
    run = AssessmentRunner().run(
        data_sources=(source,),
        spec=load_spec(root / "question.json"),
        output_directory=root / "out",
    )
    assert run.verdict is Verdict.DATA_INTEGRITY_FAILURE
