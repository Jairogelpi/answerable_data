"""Counterexamples to INV-001/002/008/010, independent of EMT's oracle."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from answerable.application.assessment_runner import AssessmentRunner, _overlap
from answerable.application.models import ClaimCandidate
from answerable.application.spec_loader import load_spec
from answerable.causal.contract import CausalContract, IdentificationStrategy
from answerable.domain.models import AnalysisType, Verdict
from answerable.domain.serialization import from_dict, to_dict
from answerable.evidence.claims import ClaimClass, ClaimContext
from answerable.evidence.verdict import FindingInput, Repairability, VerdictEngine
from tests.e2e.test_runner_edge_cases import _case


def test_INV_002_integrity_blocker_dominates_even_innocent_wording() -> None:
    blocker = FindingInput(
        "duplicate_entities",
        "data_integrity",
        "blocker",
        "duplicates",
        True,
        Repairability.RECOVERABLE,
    )
    claim = "Observed revenue was higher."
    result = VerdictEngine().decide(
        (blocker,), claims=((claim, ClaimContext(ClaimClass.DESCRIPTIVE, "customers", "2025")),)
    )
    assert result.verdict is Verdict.DATA_INTEGRITY_FAILURE
    assert result.allowed_claims == ()
    assert result.forbidden_claims == (claim,)


def test_INV_002_missing_evidence_blocks_causal_claim_without_trigger_words() -> None:
    blocker = FindingInput(
        "immature_cohort",
        "missing_evidence",
        "blocker",
        "immature",
        False,
        Repairability.RECOVERABLE,
    )
    claim = "Exposure improved retention."
    result = VerdictEngine().decide(
        (blocker,),
        claims=((claim, ClaimContext(ClaimClass.CAUSAL, "customers", "2025", causal_gate=True)),),
    )
    assert result.allowed_claims == ()
    assert result.forbidden_claims == (claim,)


def test_INV_010_partial_overlap_does_not_identify_the_whole_population(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    mapping = load_spec(root / "question.json").mapping
    rows = (
        {"treatment": "true", "acquisition_channel": "shared"},
        {"treatment": "false", "acquisition_channel": "shared"},
        {"treatment": "true", "acquisition_channel": "exclusive"},
    )
    assert not _overlap(rows, mapping)


def test_INV_008_overlap_is_not_exchangeability(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",),
        spec=load_spec(root / "question.json"),
        output_directory=root / "out",
    )
    assert run.verdict is Verdict.NOT_ANSWERABLE_YET
    assert "identification_evidence_missing" in {b.finding_id for b in run.blockers}
    assert run.allowed_claims == ()


def test_INV_009_descriptive_question_does_not_require_causal_identification(
    tmp_path: Path,
) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=8)
    spec = load_spec(root / "question.json")
    spec = replace(
        spec,
        contract=replace(spec.contract, analysis_type=AnalysisType.DESCRIPTIVE),
        claims=(ClaimCandidate("Observed group means differ.", ClaimClass.DESCRIPTIVE),),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert run.verdict is Verdict.ANSWERABLE
    assert run.allowed_claims == ("Observed group means differ.",)


def test_INV_001_findings_point_to_the_check_that_computed_them(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-06-29T00:00:00+00:00", size=8)
    AssessmentRunner().run(
        data_sources=(root / "customers.csv",),
        spec=load_spec(root / "question.json"),
        output_directory=root / "out",
    )
    graph = json.loads((root / "out/evidence_graph.json").read_text())
    edges = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "depends_on"}
    assert ("finding_immature_cohort", "chk_temporal_maturity") in edges
    assert ("finding_insufficient_power", "chk_statistical_power") in edges
    assert ("finding_immature_cohort", "chk_positivity_overlap") not in edges


def test_INV_008_assumptions_never_become_facts_and_change_identity(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    spec = load_spec(root / "question.json")
    old = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "old"
    )
    spec = replace(
        spec,
        causal=replace(spec.causal, identification_assumptions=("conditional_exchangeability",)),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "new"
    )
    assert old.assessment_id != run.assessment_id
    assert run.verdict is Verdict.ANSWERABLE_WITH_ASSUMPTIONS
    assert run.allowed_claims
    ledger = run.observations["evidence_status"]
    assert "conditional_exchangeability" in ledger["declared_assumptions"]
    assert ledger["unverifiable_conditions"]
    assert all("exchangeability" not in f["id"] for f in ledger["verified_facts"])
    graph = json.loads((root / "new/evidence_graph.json").read_text())
    assert {"fact", "assumption", "unverifiable_condition"} <= {n["type"] for n in graph["nodes"]}
    checks = {
        c["check_id"] for c in json.loads((root / "new/check_plan.json").read_text())["checks"]
    }
    assert checks == {n["id"] for n in graph["nodes"] if n["type"] == "execution"}
    assert from_dict(CausalContract, to_dict(spec.causal)) == spec.causal


def test_INV_010_assuming_exchangeability_cannot_override_missing_overlap(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    spec = load_spec(root / "question.json")
    spec = replace(
        spec,
        mapping=replace(spec.mapping, covariate_columns=("customer_id",)),
        causal=replace(
            spec.causal,
            adjustment_set=frozenset({"customer_id"}),
            identification_assumptions=("conditional_exchangeability",),
        ),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert run.verdict is Verdict.FUNDAMENTALLY_UNIDENTIFIABLE
    assert not run.allowed_claims


def test_INV_010_unchecked_adjustment_columns_block_identification(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    spec = load_spec(root / "question.json")
    spec = replace(
        spec,
        causal=replace(
            spec.causal,
            adjustment_set=frozenset({"unobserved"}),
            identification_assumptions=("conditional_exchangeability",),
        ),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert "adjustment_mapping_mismatch" in {b.finding_id for b in run.blockers}
    assert not run.allowed_claims


@pytest.mark.parametrize("levels", [(), ("a",), ("a", "b", "c"), ("a", None)])
def test_INV_010_overlap_requires_two_non_null_levels(tmp_path: Path, levels: tuple) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    mapping = replace(load_spec(root / "question.json").mapping, covariate_columns=())
    assert not _overlap(tuple({"treatment": level} for level in levels), mapping)


def test_INV_008_legacy_contract_and_invalid_assumption_schema(tmp_path: Path) -> None:
    import jsonschema

    root = _case(tmp_path, "2025-01-10T00:00:00+00:00")
    contract = load_spec(root / "question.json").causal
    assert contract.identification_assumptions == ()
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas/v1/causal-contract.schema.json").read_text()
    )
    payload = to_dict(contract)
    jsonschema.validate(payload, schema)
    payload.pop("identification_assumptions")
    jsonschema.validate(payload, schema)
    assert from_dict(CausalContract, payload) == contract
    with pytest.raises(ValueError, match="unknown identification assumption"):
        replace(contract, identification_assumptions=("overlap_proves_causality",))
    with pytest.raises(TypeError, match="frozenset"):
        from_dict(CausalContract, {**payload, "adjustment_set": "bad"})


def test_INV_008_randomization_declaration_is_also_conditional(tmp_path: Path) -> None:
    root = _case(tmp_path, "2025-01-10T00:00:00+00:00", size=160)
    spec = load_spec(root / "question.json")
    spec = replace(
        spec,
        causal=replace(
            spec.causal,
            strategy=IdentificationStrategy.RANDOMIZED,
            identification_assumptions=("random_assignment",),
        ),
    )
    run = AssessmentRunner().run(
        data_sources=(root / "customers.csv",), spec=spec, output_directory=root / "out"
    )
    assert run.verdict is Verdict.ANSWERABLE_WITH_ASSUMPTIONS
