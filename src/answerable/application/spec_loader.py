from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from answerable.application.models import AssessmentSpec, ClaimCandidate, DataMapping
from answerable.causal.contract import CausalContract, IdentificationStrategy
from answerable.domain.models import (
    AnalysisType,
    Metric,
    Population,
    QuestionContract,
    TimeWindow,
)
from answerable.evidence.claims import ClaimClass


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml  # imported here so JSON questions work without the extra

        loaded = yaml.safe_load(text)
    else:
        loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("a question file must contain a mapping")
    return loaded


def _time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("question timestamps must declare a timezone offset")
    return parsed


def load_spec(path: Path) -> AssessmentSpec:
    payload = _read(path)
    population = payload["population"]
    outcome = payload["outcome"]
    window = payload["time"]
    mapping = payload["data"]
    causal = payload["causal"]
    contract = QuestionContract(
        question_id=payload["question_id"],
        raw_question=payload["raw_question"],
        normalized_question=payload["normalized_question"],
        language=payload["language"],
        analysis_type=AnalysisType(payload["analysis_type"]),
        population=Population(
            description=population["description"],
            inclusion=tuple(population.get("inclusion", ())),
            exclusion=tuple(population.get("exclusion", ())),
        ),
        unit_of_analysis=payload["unit_of_analysis"],
        outcome=Metric(
            metric_id=outcome["metric_id"],
            definition=outcome["definition"],
            value_type=outcome["value_type"],
            numerator=outcome.get("numerator"),
            denominator=outcome.get("denominator"),
        ),
        time=TimeWindow(_time(window["observation_start"]), _time(window["observation_end"])),
        assumptions=tuple(payload.get("assumptions", ())),
        open_questions=tuple(payload.get("open_questions", ())),
    )
    return AssessmentSpec(
        contract=contract,
        mapping=DataMapping(
            entity_column=mapping["entity_column"],
            event_time_column=mapping["event_time_column"],
            treatment_column=mapping["treatment_column"],
            outcome_column=mapping["outcome_column"],
            observation_window_days=int(mapping["observation_window_days"]),
            analysis_end=_time(mapping["analysis_end"]),
            covariate_columns=tuple(mapping.get("covariate_columns", ())),
            prediction_time_column=mapping.get("prediction_time_column"),
            feature_available_time_column=mapping.get("feature_available_time_column"),
            metric_definition_column=mapping.get("metric_definition_column"),
        ),
        causal=CausalContract(
            treatment=causal["treatment"],
            outcome=causal["outcome"],
            population=causal["population"],
            estimand=causal["estimand"],
            strategy=IdentificationStrategy(causal["strategy"]),
            adjustment_set=frozenset(causal.get("adjustment_set", ())),
            assumptions=tuple(causal.get("assumptions", ())),
            falsification_checks=tuple(causal.get("falsification_checks", ())),
            sensitivity_checks=tuple(causal.get("sensitivity_checks", ())),
        ),
        claims=tuple(
            ClaimCandidate(text=item["text"], claim_class=ClaimClass(item["claim_class"]))
            for item in payload.get("claims", ())
        ),
    )


__all__ = ["load_spec"]
