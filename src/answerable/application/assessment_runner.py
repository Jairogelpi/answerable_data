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
from answerable.domain.models import AnalysisType, CheckPlan, CheckSpec, Verdict
from answerable.domain.serialization import fingerprint, to_dict
from answerable.evidence.claims import ClaimClass, ClaimContext
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
from answerable.quality.checks import DataQualityAssessor
from answerable.quality.models import Finding, Severity
from answerable.quality.temporal import TemporalAssessor, TemporalContext
from answerable.reports.markdown import render_markdown
from answerable.statistics.validity import StatisticalAssessor
from answerable.warrants.service import WarrantIssuer

_INFORMATIVE_MISSINGNESS_THRESHOLD = 0.15

_CATEGORY = {
    "causal_identification_failure": "identification",
    "identification_evidence_missing": "missing_evidence",
    "identification_assumed": "assumption",
    "missing_sensitivity": "assumption",
    "adjustment_mapping_mismatch": "missing_evidence",
    "positivity_violation": "identification",
    "immature_cohort": "missing_evidence",
    "right_censoring": "missing_evidence",
    "invalid_event_time": "data_integrity",
    "timezone_ambiguity": "data_integrity",
    "prediction_leakage": "data_integrity",
    "duplicate_entities": "data_integrity",
    "ambiguous_grain": "data_integrity",
    "insufficient_power": "power",
    "definition_change": "data_integrity",
    "informative_missingness": "missing_evidence",
}
_ALL_CLAIMS = frozenset(
    {
        "duplicate_entities",
        "prediction_leakage",
        "invalid_event_time",
        "timezone_ambiguity",
        "ambiguous_grain",
        "definition_change",
    }
)
_DESIGN_IMPOSSIBLE = frozenset({"causal_identification_failure", "positivity_violation"})
_REPAIR = {
    "identification_evidence_missing": (
        "Explicit design evidence or declared identifying assumptions.",
        "Empirical overlap alone does not establish causal identification.",
        True,
        "document the design and review identifying assumptions",
    ),
    "adjustment_mapping_mismatch": (
        "A checked covariate mapping matching the declared adjustment set.",
        "Support was not checked over the intended adjustment variables.",
        True,
        "reconcile the adjustment set with the input column mapping",
    ),
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
    "prediction_leakage": (
        "Features available only after the prediction time.",
        "A model trained on post-prediction features cannot be deployed honestly.",
        False,
        "recompute features using only information available at prediction time",
    ),
    "insufficient_power": (
        "A sample large enough to detect the claimed effect at the target power.",
        "An underpowered comparison cannot distinguish a real effect from noise.",
        True,
        "collect more observations per group, or accept a wider confidence interval",
    ),
    "definition_change": (
        "A single, stable metric definition across the whole analysis period.",
        "Comparing values computed under different definitions is not a comparison.",
        False,
        "recompute every period under one current definition, or split the analysis at the change",
    ),
    "informative_missingness": (
        "Outcome missingness that does not depend on the treatment assignment.",
        "When missingness itself differs by treatment, the observed difference is confounded "
        "with who got measured, not just who got treated.",
        True,
        "follow up on missing outcomes so measurement no longer depends on treatment",
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


_FINDING_CHECK = {
    "duplicate_entities": "chk_grain_uniqueness",
    "ambiguous_grain": "chk_grain_uniqueness",
    "invalid_event_time": "chk_temporal_maturity",
    "timezone_ambiguity": "chk_temporal_maturity",
    "immature_cohort": "chk_temporal_maturity",
    "right_censoring": "chk_temporal_maturity",
    "prediction_leakage": "chk_temporal_maturity",
    "definition_change": "chk_metric_definition",
    "informative_missingness": "chk_outcome_missingness",
    "insufficient_power": "chk_statistical_power",
    "positivity_violation": "chk_positivity_overlap",
    "causal_identification_failure": "chk_causal_identification",
    "identification_evidence_missing": "chk_causal_identification",
    "identification_assumed": "chk_causal_identification",
    "adjustment_mapping_mismatch": "chk_causal_identification",
    "missing_sensitivity": "chk_causal_identification",
}
_EXTRA_CHECKS = tuple(
    CheckSpec(
        check_id=check_id,
        check_type=kind,
        check_version="1.0",
        requirement_id=requirement,
        executor="python",
        severity_on_failure="blocker",
        rationale=rationale,
        mandatory=True,
    )
    for check_id, kind, requirement, rationale in (
        (
            "chk_metric_definition",
            "metric.definition",
            "INV-009",
            "Check stable metric definitions.",
        ),
        (
            "chk_outcome_missingness",
            "quality.missingness",
            "INV-009",
            "Compare outcome missingness by group.",
        ),
        (
            "chk_statistical_power",
            "statistical.power",
            "INV-005",
            "Assess inferential precision limitations.",
        ),
        ("chk_observed_means", "descriptive.means", "INV-001", "Compute observed group means."),
    )
)


def _requires_causal(spec: AssessmentSpec) -> bool:
    return spec.contract.analysis_type is AnalysisType.CAUSAL or any(
        claim.claim_class is ClaimClass.CAUSAL for claim in spec.claims
    )


def _checks_for(spec: AssessmentSpec) -> tuple[CheckSpec, ...]:
    checks = list(_CHECKS[:2])
    if _requires_causal(spec):
        checks.extend(_CHECKS[2:])
    for check in _EXTRA_CHECKS:
        if check.check_id == "chk_metric_definition" and not spec.mapping.metric_definition_column:
            continue
        if (
            check.check_id == "chk_statistical_power"
            and spec.contract.analysis_type is AnalysisType.DESCRIPTIVE
            and not _requires_causal(spec)
        ):
            continue
        checks.append(check)
    return tuple(checks)


def _evidence_status(
    spec: AssessmentSpec, rows: tuple[dict[str, object], ...], findings: tuple[Finding, ...]
) -> dict[str, Any]:
    facts: list[dict[str, object]] = [
        {"id": "row_count", "value": len(rows), "check_id": "chk_grain_uniqueness"},
        {
            "id": "unique_entities",
            "value": len({r["entity"] for r in rows}) == len(rows),
            "check_id": "chk_grain_uniqueness",
        },
    ]
    if _requires_causal(spec):
        facts.append(
            {
                "id": "empirical_stratum_overlap",
                "value": _overlap(rows, spec.mapping),
                "check_id": "chk_positivity_overlap",
            }
        )
    assumptions = list(
        dict.fromkeys(
            (
                *spec.contract.assumptions,
                *spec.causal.assumptions,
                *spec.causal.identification_assumptions,
            )
        )
    )
    return {
        "verified_facts": facts,
        "declared_assumptions": assumptions,
        "unverifiable_conditions": (
            [
                "Absence of unmeasured confounding is not established by observed overlap.",
                "The declared design assumptions require evidence beyond this table.",
            ]
            if _requires_causal(spec)
            else []
        ),
        "conditional_identification": any(f.code == "identification_assumed" for f in findings),
    }


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
                    "spec": to_dict(spec),
                    "sources": [item.fingerprint for item in snapshots],
                }
            )[:16]
        )

        primary = Path(snapshots[0].path)
        rows = _load(primary, spec.mapping)
        descriptive = _describe(primary, spec.mapping)

        findings = _run_checks(snapshots[0], rows, descriptive, spec)
        finding_inputs = tuple(_to_finding_input(item) for item in findings)
        identified = _requires_causal(spec) and not any(
            item.code
            in _DESIGN_IMPOSSIBLE
            | {"identification_evidence_missing", "adjustment_mapping_mismatch"}
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
        status = _evidence_status(spec, rows, findings)
        graph = _build_graph(spec, snapshots, descriptive, findings, verdict, status)
        observations = {
            "identified": identified,
            "outcome_rates": [
                {"group": group, "entities": count, "rate": rate}
                for group, count, rate in descriptive.by_group
            ],
            "observed_difference": descriptive.difference,
            "baseline": descriptive.baseline,
            "evidence_status": status,
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
        # try_cast, not cast: a blank or non-numeric outcome is a missing value to
        # report, not a reason to abort the whole run.
        f"try_cast({_identifier(mapping.outcome_column)} AS DOUBLE) AS outcome",
    ]
    columns += [
        f"cast({_identifier(name)} AS VARCHAR) AS {_identifier(name)}"
        for name in mapping.covariate_columns
    ]
    optional_time_columns = {
        "prediction_time": mapping.prediction_time_column,
        "feature_available_time": mapping.feature_available_time_column,
    }
    for alias, source in optional_time_columns.items():
        if source:
            columns.append(f"cast({_identifier(source)} AS VARCHAR) AS {alias}")
    if mapping.metric_definition_column:
        columns.append(
            f"cast({_identifier(mapping.metric_definition_column)} AS VARCHAR) AS metric_definition"
        )
    with duckdb.connect() as connection:
        cursor = connection.execute(
            f"SELECT {', '.join(columns)} FROM {_relation(path)} ORDER BY 1"
        )
        names = [item[0] for item in cursor.description or ()]
        records = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    for record in records:
        record["event_time"] = _parse_time(record["event_time"])
        for alias in optional_time_columns:
            if alias in record:
                record[alias] = _parse_time(record[alias])
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
            f"SELECT cast({treatment} AS VARCHAR), count(*), avg(try_cast({outcome} AS DOUBLE)) "
            f"FROM {_relation(path)} GROUP BY 1 ORDER BY 1"
        ).fetchall()
    by_group = tuple((str(row[0]), int(row[1]), float(row[2])) for row in rows)
    if len(by_group) != 2:
        return _Descriptive(by_group, None, None)
    baseline = by_group[0][2]
    return _Descriptive(by_group, by_group[1][2] - baseline, baseline)


def _overlap(rows: tuple[dict[str, object], ...], mapping: DataMapping) -> bool:
    """Conservative binary support check over every declared target stratum.

    Empirical support is not proof of population positivity or exchangeability.
    Continuous covariates require an explicitly reviewed coarsening upstream.
    """
    strata: dict[tuple[object, ...], set[object]] = {}
    for row in rows:
        key = tuple(row.get(name) for name in mapping.covariate_columns)
        strata.setdefault(key, set()).add(row["treatment"])
    levels = {row["treatment"] for row in rows}
    return (
        len(levels) == 2
        and None not in levels
        and bool(strata)
        and all(values == levels for values in strata.values())
        and all(None not in key for key in strata)
    )


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
                prediction_time=(
                    "prediction_time" if spec.mapping.prediction_time_column else None
                ),
                feature_available_time=(
                    "feature_available_time" if spec.mapping.feature_available_time_column else None
                ),
                observation_window=timedelta(days=spec.mapping.observation_window_days),
                analysis_end=spec.mapping.analysis_end,
            ),
        )
    )
    if spec.mapping.metric_definition_column:
        versions = tuple(
            (row["event_time"], str(row["metric_definition"]))
            for row in rows
            if isinstance(row["event_time"], datetime)
        )
        findings.extend(TemporalAssessor.definition_changes(versions))
    findings.extend(_missingness_findings(rows, spec.mapping))

    if _requires_causal(spec):
        overlap = _overlap(rows, spec.mapping)
        if not overlap:
            findings.append(
                Finding(
                    "positivity_violation",
                    Severity.BLOCKER,
                    "Every target covariate stratum must contain both binary treatment levels.",
                    (spec.mapping.treatment_column, *spec.mapping.covariate_columns),
                )
            )
        mapping_matches = spec.causal.adjustment_set == frozenset(spec.mapping.covariate_columns)
        if not mapping_matches:
            findings.append(
                Finding(
                    "adjustment_mapping_mismatch",
                    Severity.BLOCKER,
                    "Declared adjustment set differs from the checked covariates.",
                )
            )
        declared = set(spec.causal.identification_assumptions)
        causal = CausalIdentifier().assess(
            spec.causal,
            _ObservedDifferenceEstimator(descriptive),
            positivity_supported=overlap,
            exchangeability_supported="conditional_exchangeability" in declared and mapping_matches,
            randomization_valid="random_assignment" in declared,
            parallel_trends_supported="parallel_trends" in declared,
            instrument_valid="valid_instrument" in declared,
            discontinuity_valid="valid_discontinuity" in declared,
        )
        for finding in causal.findings:
            if finding.code == "causal_identification_failure" and overlap:
                findings.append(
                    Finding(
                        "identification_evidence_missing",
                        Severity.BLOCKER,
                        "Identifying conditions are neither established nor explicitly assumed.",
                    )
                )
            else:
                findings.append(finding)
        if causal.identified:
            findings.append(
                Finding(
                    "identification_assumed",
                    Severity.WARNING,
                    "Identification is conditional on declared assumptions. "
                    "Not verified: the mean difference remains descriptive, not adjusted.",
                )
            )
    if spec.contract.analysis_type is not AnalysisType.DESCRIPTIVE or _requires_causal(spec):
        findings.extend(_power_findings(rows))
    return tuple(findings)


def _power_findings(rows: tuple[dict[str, object], ...]) -> tuple[Finding, ...]:
    """Is this comparison's sample large enough to trust a null result?

    A moderate observed effect from a handful of observations per group can
    be statistical noise; StatisticalAssessor reports insufficient_power
    when the achieved power falls short of the 80% target.
    """
    by_treatment: dict[object, list[float]] = {}
    for row in rows:
        outcome = row.get("outcome")
        if isinstance(outcome, (int, float)):
            by_treatment.setdefault(row["treatment"], []).append(float(outcome))
    groups = sorted(by_treatment.items(), key=lambda item: str(item[0]))
    if len(groups) != 2 or any(len(values) < 2 for _, values in groups):
        return ()
    (_, control), (_, treatment) = groups
    return StatisticalAssessor().assess_mean_difference(tuple(treatment), tuple(control)).findings


def _missingness_findings(
    rows: tuple[dict[str, object], ...], mapping: DataMapping
) -> tuple[Finding, ...]:
    """Does outcome missingness itself depend on treatment assignment?

    Equal missingness across arms just shrinks the sample (see
    _power_findings). Missingness that differs by arm confounds the
    comparison with who got measured, not just who got treated -- that is
    a validity failure a bigger sample does not fix.
    """
    rates = DataQualityAssessor.missingness_by_group(rows, field="outcome", group="treatment")
    if len(rates) != 2:
        return ()
    spread = max(rates.values()) - min(rates.values())
    if spread <= _INFORMATIVE_MISSINGNESS_THRESHOLD:
        return ()
    return (
        Finding(
            "informative_missingness",
            Severity.BLOCKER,
            "Outcome missingness rate differs by treatment arm.",
            (mapping.treatment_column, mapping.outcome_column),
            spread,
        ),
    )


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
    status: dict[str, Any],
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
    for check in _checks_for(spec):
        store.add_node(GraphNode(check.check_id, NodeType.EXECUTION, {"type": check.check_type}))
        store.add_edge(GraphEdge(check.check_id, snapshots[0].asset_id, EdgeType.USES))
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
    store.add_edge(GraphEdge("obs_outcome_rates", "chk_observed_means", EdgeType.COMPUTED_FROM))
    for finding in findings:
        node_type = NodeType.BLOCKER if finding.severity is Severity.BLOCKER else NodeType.WARNING
        store.add_node(
            GraphNode(f"finding_{finding.code}", node_type, {"message": finding.message})
        )
        store.add_edge(
            GraphEdge(f"finding_{finding.code}", _FINDING_CHECK[finding.code], EdgeType.DEPENDS_ON)
        )
    for index, fact in enumerate(status["verified_facts"]):
        node_id = f"fact_{index}"
        store.add_node(GraphNode(node_id, NodeType.FACT, fact))
        store.add_edge(GraphEdge(node_id, str(fact["check_id"]), EdgeType.COMPUTED_FROM))
    for key, node_type in (
        ("declared_assumptions", NodeType.ASSUMPTION),
        ("unverifiable_conditions", NodeType.UNVERIFIABLE_CONDITION),
    ):
        for index, statement in enumerate(status[key]):
            store.add_node(GraphNode(f"{key}_{index}", node_type, {"statement": statement}))
    for index, claim in enumerate(verdict.allowed_claims):
        node = f"claim_allowed_{index}"
        store.add_node(GraphNode(node, NodeType.ALLOWED_CLAIM, {"text": claim}))
        store.add_edge(GraphEdge(node, "obs_outcome_rates", EdgeType.DEPENDS_ON))
        for index in range(len(status["declared_assumptions"])):
            store.add_edge(GraphEdge(node, f"declared_assumptions_{index}", EdgeType.ASSUMES))
    for index, claim in enumerate(verdict.forbidden_claims):
        node = f"claim_forbidden_{index}"
        store.add_node(GraphNode(node, NodeType.FORBIDDEN_CLAIM, {"text": claim}))
        for finding in findings:
            candidate = next(candidate for candidate in spec.claims if candidate.text == claim)
            if VerdictEngine.blocks_claim(_to_finding_input(finding), candidate.claim_class):
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
        "assumptions": list(
            dict.fromkeys(
                (
                    *spec.contract.assumptions,
                    *spec.causal.assumptions,
                    *spec.causal.identification_assumptions,
                )
            )
        ),
        "limitations": [item.message for item in findings if item.severity is Severity.WARNING],
        "data_quality_relevance": observations,
        "minimum_evidence_plan": {
            "candidates": [to_dict(item) for item in candidates],
            "minimal": to_dict(minimal) if minimal else None,
        },
        "permitted_analysis": (
            "only the listed allowed claims; no adjusted causal estimate is computed"
            if verdict.allowed_claims
            else "none"
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
            "checks": [to_dict(item) for item in _checks_for(spec)],
            "evidence_graph_hash": graph["content_hash"],
        },
        "approvals": [],
        "supersession_status": "current",
    }


def _explain(verdict: Verdict, findings: tuple[Finding, ...]) -> str:
    blockers = [item.message for item in findings if item.severity is Severity.BLOCKER]
    if verdict is Verdict.ANSWERABLE_WITH_ASSUMPTIONS:
        return (
            "The conclusion is conditional on declared assumptions; these are not verified facts."
        )
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
                checks=_checks_for(spec),
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
