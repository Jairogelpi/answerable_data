from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

from answerable.analysis.grain import GrainAnalyzer, GrainStatus
from answerable.application.models import AssessmentRun, AssessmentSpec, DataMapping
from answerable.causal.contract import CausalContract, CausalIdentifier
from answerable.domain.models import CheckPlan, CheckSpec, Verdict
from answerable.domain.serialization import fingerprint, to_dict
from answerable.evidence.claims import ClaimContext
from answerable.evidence.graph import (
    EdgeType,
    EvidenceGraphStore,
    GraphEdge,
    GraphNode,
    NodeType,
)
from answerable.evidence.verdict import (
    FindingInput,
    Repairability,
    RepairItem,
    RepairPlanGenerator,
    VerdictEngine,
    VerdictResult,
)
from answerable.ingestion.files import FileInspector
from answerable.ingestion.models import DataAssetSnapshot
from answerable.quality.models import Finding, Severity
from answerable.quality.temporal import TemporalAssessor, TemporalContext
from answerable.reports.markdown import render_markdown
from answerable.warrants.service import WarrantIssuer

_CATEGORY = {
    "causal_identification_failure": "identification",
    "positivity_violation": "identification",
    "immature_cohort": "missing_evidence",
    "right_censoring": "missing_evidence",
    "invalid_event_time": "data_integrity",
    "timezone_ambiguity": "data_integrity",
    "prediction_leakage": "data_integrity",
    "duplicate_entities": "data_integrity",
    "ambiguous_grain": "data_integrity",
}
_ALL_CLAIMS = frozenset(
    {
        "duplicate_entities",
        "prediction_leakage",
        "invalid_event_time",
        "timezone_ambiguity",
        "ambiguous_grain",
    }
)
_DESIGN_IMPOSSIBLE = frozenset({"causal_identification_failure", "positivity_violation"})
_REPAIR = {
    "causal_identification_failure": (
        "A comparison population that identifies the requested causal estimand.",
        "Without it no observed difference can be attributed to the campaign.",
        False,
        "randomized holdout or a quasi-experimental design with overlap",
    ),
    "positivity_violation": (
        "Exposed and unexposed customers inside the same covariate stratum.",
        "With zero overlap no adjustment can remove confounding.",
        False,
        "randomized holdout, or exposure that varies within each stratum",
    ),
    "immature_cohort": (
        "Outcome observation for entities that have not completed the window.",
        "Immature cohorts understate retention and bias the comparison.",
        True,
        "wait until every cohort completes the observation window",
    ),
    "right_censoring": (
        "Outcome labels that are still unavailable at the analysis cutoff.",
        "Censored outcomes are not missing at random.",
        True,
        "extend the label collection window",
    ),
}
_CHECKS = (
    CheckSpec(
        check_id="chk_grain_uniqueness",
        check_type="grain.uniqueness",
        check_version="1.0",
        requirement_id="req_unit_of_analysis",
        executor="duckdb",
        severity_on_failure="blocker",
        rationale="The declared unit of analysis must identify one row.",
        mandatory=True,
    ),
    CheckSpec(
        check_id="chk_temporal_maturity",
        check_type="temporal.maturity",
        check_version="1.0",
        requirement_id="req_observation_window",
        executor="python",
        severity_on_failure="blocker",
        rationale="Every entity must complete the observation window.",
        mandatory=True,
    ),
    CheckSpec(
        check_id="chk_positivity_overlap",
        check_type="causal.positivity",
        check_version="1.0",
        requirement_id="req_comparison_population",
        executor="duckdb",
        severity_on_failure="blocker",
        rationale="Both treatment levels must occur inside a covariate stratum.",
        mandatory=True,
    ),
    CheckSpec(
        check_id="chk_causal_identification",
        check_type="causal.identification",
        check_version="1.0",
        requirement_id="req_identification_strategy",
        executor="python",
        severity_on_failure="blocker",
        dependencies=("chk_positivity_overlap",),
        rationale="The declared strategy must be supported by the observed design.",
        mandatory=True,
    ),
)


@dataclass(frozen=True, slots=True)
class _Descriptive:
    """Group rates for the declared outcome. Descriptive only, never causal."""

    by_group: tuple[tuple[str, int, float], ...]
    difference: float | None
    baseline: float | None


class _ObservedDifferenceEstimator:
    def __init__(self, descriptive: _Descriptive) -> None:
        self._descriptive = descriptive

    def estimate(self, contract: CausalContract) -> float:
        del contract
        return self._descriptive.difference or 0.0


class AssessmentRunner:
    """Wires ingestion, checks, evidence, verdict and warrant into one run."""

    def __init__(self, *, secret: bytes | None = None, signer: str | None = None) -> None:
        self._secret = secret
        self._signer = signer

    def run(
        self,
        *,
        data_sources: tuple[Path, ...],
        spec: AssessmentSpec,
        output_directory: Path,
    ) -> AssessmentRun:
        if not data_sources:
            raise ValueError("at least one data source is required")
        inspector = FileInspector()
        try:
            snapshots = tuple(inspector.inspect(path) for path in data_sources)
        finally:
            inspector.close()

        assessment_id = (
            "asm_"
            + fingerprint(
                {
                    "question": to_dict(spec.contract),
                    "sources": [item.fingerprint for item in snapshots],
                }
            )[:16]
        )

        primary = Path(snapshots[0].path)
        rows = _load(primary, spec.mapping)
        descriptive = _describe(primary, spec.mapping)

        findings = _run_checks(snapshots[0], rows, descriptive, spec)
        finding_inputs = tuple(_to_finding_input(item) for item in findings)
        identified = not any(
            item.code in _DESIGN_IMPOSSIBLE
            for item in findings
            if item.severity is Severity.BLOCKER
        )
        claims = tuple(
            (
                candidate.text,
                ClaimContext(
                    claim_class=candidate.claim_class,
                    population=spec.contract.population.description,
                    period=(
                        f"{spec.contract.time.observation_start.date()}"
                        f"/{spec.contract.time.observation_end.date()}"
                    ),
                    baseline=descriptive.baseline,
                    causal_gate=identified,
                ),
            )
            for candidate in spec.claims
        )
        verdict = VerdictEngine().decide(finding_inputs, claims=claims)

        repairs = _repair_plan(findings)
        graph = _build_graph(spec, snapshots, descriptive, findings, verdict)
        observations = {
            "identified": identified,
            "outcome_rates": [
                {"group": group, "entities": count, "rate": rate}
                for group, count, rate in descriptive.by_group
            ],
            "observed_difference": descriptive.difference,
            "baseline": descriptive.baseline,
        }
        payload = _warrant_payload(
            assessment_id, spec, snapshots, verdict, findings, repairs, observations, graph
        )
        warrant = WarrantIssuer().issue(
            f"wrt_{assessment_id.removeprefix('asm_')}",
            1,
            payload,
            signer=self._signer,
            secret=self._secret,
        )

        run = AssessmentRun(
            assessment_id=assessment_id,
            verdict=verdict.verdict,
            blockers=tuple(
                item for item in finding_inputs if item.severity in {"blocker", "fatal"}
            ),
            allowed_claims=verdict.allowed_claims,
            forbidden_claims=verdict.forbidden_claims,
            observations=observations,
            warrant=warrant,
            artifacts={},
        )
        artifacts = _write(
            output_directory,
            spec,
            snapshots,
            assessment_id,
            findings,
            graph,
            verdict,
            repairs,
            run,
        )
        return AssessmentRun(
            assessment_id=run.assessment_id,
            verdict=run.verdict,
            blockers=run.blockers,
            allowed_claims=run.allowed_claims,
            forbidden_claims=run.forbidden_claims,
            observations=run.observations,
            warrant=run.warrant,
            artifacts=artifacts,
        )


def _relation(path: Path) -> str:
    escaped = str(path).replace("'", "''")
    if path.suffix.lower() == ".parquet":
        return f"read_parquet('{escaped}')"
    return f"read_csv_auto('{escaped}', sample_size=-1)"


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _load(path: Path, mapping: DataMapping) -> tuple[dict[str, object], ...]:
    columns = [
        f"cast({_identifier(mapping.entity_column)} AS VARCHAR) AS entity",
        # read as text and parse in Python: duckdb's TIMESTAMPTZ conversion needs pytz
        f"cast({_identifier(mapping.event_time_column)} AS VARCHAR) AS event_time",
        f"cast({_identifier(mapping.treatment_column)} AS VARCHAR) AS treatment",
        f"cast({_identifier(mapping.outcome_column)} AS DOUBLE) AS outcome",
    ]
    columns += [
        f"cast({_identifier(name)} AS VARCHAR) AS {_identifier(name)}"
        for name in mapping.covariate_columns
    ]
    with duckdb.connect() as connection:
        cursor = connection.execute(
            f"SELECT {', '.join(columns)} FROM {_relation(path)} ORDER BY 1"
        )
        names = [item[0] for item in cursor.description or ()]
        records = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    for record in records:
        record["event_time"] = _parse_time(record["event_time"])
    return tuple(records)


def _parse_time(value: object) -> object:
    """Keep the raw value when it is not a timestamp: the temporal check reports it."""
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return value


def _describe(path: Path, mapping: DataMapping) -> _Descriptive:
    treatment = _identifier(mapping.treatment_column)
    outcome = _identifier(mapping.outcome_column)
    with duckdb.connect() as connection:
        rows = connection.execute(
            f"SELECT cast({treatment} AS VARCHAR), count(*), avg(cast({outcome} AS DOUBLE)) "
            f"FROM {_relation(path)} GROUP BY 1 ORDER BY 1"
        ).fetchall()
    by_group = tuple((str(row[0]), int(row[1]), float(row[2])) for row in rows)
    if len(by_group) != 2:
        return _Descriptive(by_group, None, None)
    baseline = by_group[0][2]
    return _Descriptive(by_group, by_group[1][2] - baseline, baseline)


def _overlap(rows: tuple[dict[str, object], ...], mapping: DataMapping) -> bool:
    """Positivity: some stratum must contain both treatment levels."""
    strata: dict[tuple[object, ...], set[object]] = {}
    for row in rows:
        key = tuple(row.get(name) for name in mapping.covariate_columns)
        strata.setdefault(key, set()).add(row["treatment"])
    return any(len(levels) > 1 for levels in strata.values())


def _run_checks(
    snapshot: DataAssetSnapshot,
    rows: tuple[dict[str, object], ...],
    descriptive: _Descriptive,
    spec: AssessmentSpec,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    grain = GrainAnalyzer().infer(snapshot.profile)
    entities = {row["entity"] for row in rows}
    if len(entities) != len(rows):
        findings.append(
            Finding(
                "duplicate_entities",
                Severity.BLOCKER,
                "The declared unit of analysis does not identify one row.",
                (spec.mapping.entity_column,),
                len(rows) - len(entities),
            )
        )
    elif grain.status is GrainStatus.NO_KEY:
        findings.append(
            Finding(
                "ambiguous_grain",
                Severity.WARNING,
                "No column uniquely identifies a row in the raw file.",
            )
        )

    findings.extend(
        TemporalAssessor().assess(
            rows,
            context=TemporalContext(
                event_time="event_time",
                observation_window=timedelta(days=spec.mapping.observation_window_days),
                analysis_end=spec.mapping.analysis_end,
            ),
        )
    )

    overlap = _overlap(rows, spec.mapping)
    if not overlap:
        findings.append(
            Finding(
                "positivity_violation",
                Severity.BLOCKER,
                "No covariate stratum contains both exposed and unexposed entities.",
                (spec.mapping.treatment_column, *spec.mapping.covariate_columns),
            )
        )
    findings.extend(
        CausalIdentifier()
        .assess(
            spec.causal,
            _ObservedDifferenceEstimator(descriptive),
            positivity_supported=overlap,
            exchangeability_supported=overlap,
        )
        .findings
    )
    return tuple(findings)


def _to_finding_input(finding: Finding) -> FindingInput:
    category = _CATEGORY.get(finding.code, "partial")
    severity = finding.severity.value
    repairability = None
    if finding.severity is Severity.BLOCKER:
        repairability = (
            Repairability.DESIGN_IMPOSSIBLE
            if finding.code in _DESIGN_IMPOSSIBLE
            else Repairability.RECOVERABLE
        )
    return FindingInput(
        finding_id=finding.code,
        category=category,
        severity=severity,
        message=finding.message,
        affects_all_claims=finding.code in _ALL_CLAIMS,
        repairability=repairability,
    )


def _repair_plan(findings: tuple[Finding, ...]) -> tuple[tuple[RepairItem, ...], RepairItem | None]:
    candidates: list[RepairItem] = []
    for index, finding in enumerate(findings):
        if finding.severity is not Severity.BLOCKER or finding.code not in _REPAIR:
            continue
        missing, why, retrospective, method = _REPAIR[finding.code]
        candidates.append(
            RepairItem(
                missing_information=missing,
                why_it_matters=why,
                retrospective=retrospective,
                collection_method=method,
                required_grain="one row per entity",
                required_population="the declared analysis population",
                minimum_time_window="one full observation window",
                sample_size_target=None,
                expected_verdict_effect=(
                    "Removes this blocker; the verdict may still depend on others."
                ),
                cost=index + 1,
                priority=1 if not retrospective else 2,
                alternative_question=(
                    "What was the observed difference, without attributing it to a cause?"
                ),
            )
        )
    minimal = RepairPlanGenerator().minimal(tuple(candidates))
    return tuple(candidates), minimal[0] if minimal else None


def _build_graph(
    spec: AssessmentSpec,
    snapshots: tuple[DataAssetSnapshot, ...],
    descriptive: _Descriptive,
    findings: tuple[Finding, ...],
    verdict: VerdictResult,
) -> dict[str, object]:
    store = EvidenceGraphStore()
    store.add_node(
        GraphNode(
            "question",
            NodeType.QUESTION,
            {"text": spec.contract.normalized_question, "type": spec.contract.analysis_type.value},
        )
    )
    for snapshot in snapshots:
        store.add_node(
            GraphNode(
                snapshot.asset_id,
                NodeType.DATASET,
                {
                    "path": Path(snapshot.path).name,
                    "fingerprint": snapshot.fingerprint,
                    "rows": snapshot.row_count,
                },
            )
        )
    for check in _CHECKS:
        store.add_node(GraphNode(check.check_id, NodeType.EXECUTION, {"type": check.check_type}))
        for snapshot in snapshots:
            store.add_edge(GraphEdge(check.check_id, snapshot.asset_id, EdgeType.USES))
    store.add_node(
        GraphNode(
            "obs_outcome_rates",
            NodeType.OBSERVATION,
            {
                "by_group": [
                    {"group": g, "entities": n, "rate": r} for g, n, r in descriptive.by_group
                ],
                "difference": descriptive.difference,
            },
        )
    )
    store.add_edge(GraphEdge("obs_outcome_rates", "chk_grain_uniqueness", EdgeType.COMPUTED_FROM))
    for finding in findings:
        node_type = NodeType.BLOCKER if finding.severity is Severity.BLOCKER else NodeType.WARNING
        store.add_node(
            GraphNode(f"finding_{finding.code}", node_type, {"message": finding.message})
        )
        store.add_edge(
            GraphEdge(f"finding_{finding.code}", "chk_positivity_overlap", EdgeType.DEPENDS_ON)
        )
    for index, claim in enumerate(verdict.allowed_claims):
        node = f"claim_allowed_{index}"
        store.add_node(GraphNode(node, NodeType.ALLOWED_CLAIM, {"text": claim}))
        store.add_edge(GraphEdge(node, "obs_outcome_rates", EdgeType.DEPENDS_ON))
    for index, claim in enumerate(verdict.forbidden_claims):
        node = f"claim_forbidden_{index}"
        store.add_node(GraphNode(node, NodeType.FORBIDDEN_CLAIM, {"text": claim}))
        for finding in findings:
            if finding.severity is Severity.BLOCKER:
                store.add_edge(GraphEdge(f"finding_{finding.code}", node, EdgeType.BLOCKS))
    store.validate_claims()
    return store.export()


def _warrant_payload(
    assessment_id: str,
    spec: AssessmentSpec,
    snapshots: tuple[DataAssetSnapshot, ...],
    verdict: VerdictResult,
    findings: tuple[Finding, ...],
    repairs: tuple[tuple[RepairItem, ...], RepairItem | None],
    observations: dict[str, object],
    graph: dict[str, object],
) -> dict[str, Any]:
    candidates, minimal = repairs
    return {
        "identity": {"assessment_id": assessment_id, "schema_version": "1.0"},
        "question": to_dict(spec.contract),
        "decision_context": {
            "unit_of_analysis": spec.contract.unit_of_analysis,
            "estimand": spec.causal.estimand,
            "strategy": spec.causal.strategy.value,
        },
        "verdict": verdict.verdict.value,
        "executive_explanation": _explain(verdict.verdict, findings),
        "allowed_claims": list(verdict.allowed_claims),
        "forbidden_claims": list(verdict.forbidden_claims),
        "decisive_evidence": [
            {"code": item.finding_id, "category": item.category, "message": item.message}
            for item in verdict.decisive_findings
        ],
        "assumptions": list(spec.causal.assumptions),
        "limitations": [item.message for item in findings if item.severity is Severity.WARNING],
        "data_quality_relevance": observations,
        "minimum_evidence_plan": {
            "candidates": [to_dict(item) for item in candidates],
            "minimal": to_dict(minimal) if minimal else None,
        },
        "permitted_analysis": (
            "descriptive comparison only"
            if verdict.verdict is not Verdict.ANSWERABLE
            else "full analysis"
        ),
        "provenance": [
            {
                "path": Path(item.path).name,
                "fingerprint": item.fingerprint,
                "rows": item.row_count,
                "bytes": item.byte_size,
            }
            for item in snapshots
        ],
        "reproducibility_manifest": {
            "checks": [to_dict(item) for item in _CHECKS],
            "evidence_graph_hash": graph["content_hash"],
        },
        "approvals": [],
        "supersession_status": "current",
    }


def _explain(verdict: Verdict, findings: tuple[Finding, ...]) -> str:
    blockers = [item.message for item in findings if item.severity is Severity.BLOCKER]
    if not blockers:
        return "The available evidence supports the requested conclusion."
    return (
        f"The verdict is {verdict.value} because the available data cannot support the "
        f"requested conclusion: {' '.join(blockers)}"
    )


def _write(
    directory: Path,
    spec: AssessmentSpec,
    snapshots: tuple[DataAssetSnapshot, ...],
    assessment_id: str,
    findings: tuple[Finding, ...],
    graph: dict[str, object],
    verdict: VerdictResult,
    repairs: tuple[tuple[RepairItem, ...], RepairItem | None],
    run: AssessmentRun,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    candidates, minimal = repairs
    documents: dict[str, object] = {
        "question_contract": to_dict(spec.contract),
        "data_inventory": [to_dict(item) for item in snapshots],
        "check_plan": to_dict(
            CheckPlan(
                plan_id=f"pln_{assessment_id.removeprefix('asm_')}",
                assessment_id=assessment_id,
                checks=_CHECKS,
            )
        ),
        "findings": [to_dict(item) for item in findings],
        "evidence_graph": graph,
        "verdict": {
            "assessment_id": assessment_id,
            "verdict": verdict.verdict.value,
            "allowed_claims": list(verdict.allowed_claims),
            "forbidden_claims": list(verdict.forbidden_claims),
            "blockers": [to_dict(item) for item in run.blockers],
        },
        "repair_plan": {
            "candidates": [to_dict(item) for item in candidates],
            "minimal": to_dict(minimal) if minimal else None,
        },
        "warrant": to_dict(run.warrant),
    }
    artifacts: dict[str, Path] = {}
    for name, document in documents.items():
        target = directory / f"{name}.json"
        target.write_text(
            json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        artifacts[name] = target
    markdown = directory / "warrant.md"
    markdown.write_text(render_markdown(run), encoding="utf-8")
    artifacts["warrant_markdown"] = markdown
    return artifacts


def load_warrant(path: Path) -> Any:
    """Rebuild a WarrantRecord written by a run, for verification."""
    from answerable.domain.serialization import from_dict
    from answerable.warrants.service import WarrantRecord

    payload = json.loads(path.read_text(encoding="utf-8"))
    return from_dict(WarrantRecord, payload)


__all__ = ["AssessmentRunner", "load_warrant"]
