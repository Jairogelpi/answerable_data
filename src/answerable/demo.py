from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.models import AssessmentRun
from answerable.application.spec_loader import load_spec


@dataclass(frozen=True, slots=True)
class DemoCase:
    name: str
    title: str
    question: str
    trap: str
    expected_signal: str
    csv: str


_BASE_ROWS = """customer_id,acquisition_date,campaign_exposed,retained_90d,acquisition_channel
c01,2025-01-01T00:00:00+00:00,0,0,organic
c02,2025-01-02T00:00:00+00:00,0,1,organic
c03,2025-01-03T00:00:00+00:00,0,0,organic
c04,2025-01-04T00:00:00+00:00,0,1,organic
c05,2025-01-01T00:00:00+00:00,1,1,paid
c06,2025-01-02T00:00:00+00:00,1,1,paid
c07,2025-01-03T00:00:00+00:00,1,0,paid
c08,2025-01-04T00:00:00+00:00,1,1,paid
"""

_MATURITY_ROWS = """customer_id,acquisition_date,campaign_exposed,retained_90d,acquisition_channel
m01,2025-01-01T00:00:00+00:00,0,0,mixed
m02,2025-01-02T00:00:00+00:00,0,1,mixed
m03,2025-01-03T00:00:00+00:00,1,1,mixed
m04,2025-01-04T00:00:00+00:00,1,1,mixed
m05,2025-05-15T00:00:00+00:00,0,0,mixed
m06,2025-05-16T00:00:00+00:00,1,1,mixed
"""

CASES: dict[str, DemoCase] = {
    "causal": DemoCase(
        name="causal",
        title="Causal attribution trap",
        question="Did campaign exposure increase 90-day retention?",
        trap="The observed difference is real, but treatment has zero covariate overlap.",
        expected_signal="positivity_violation",
        csv=_BASE_ROWS,
    ),
    "grain": DemoCase(
        name="grain",
        title="Duplicate unit-of-analysis trap",
        question="Did campaign exposure increase 90-day retention?",
        trap="A duplicated customer violates the declared one-row-per-customer grain.",
        expected_signal="duplicate_entities",
        csv=_BASE_ROWS + "c08,2025-01-04T00:00:00+00:00,1,1,paid\n",
    ),
    "maturity": DemoCase(
        name="maturity",
        title="Immature cohort trap",
        question="Did campaign exposure increase 90-day retention?",
        trap="Recent customers have not completed the required 90-day observation window.",
        expected_signal="immature_cohort",
        csv=_MATURITY_ROWS,
    ),
}


def _question_yaml(case: DemoCase) -> str:
    return f'''question_id: q_demo_{case.name}
raw_question: "{case.question}"
normalized_question: "{case.question}"
language: en
analysis_type: causal
unit_of_analysis: customer
population:
  description: "Customers in the built-in {case.name} demonstration"
  inclusion: ["rows in the bundled demonstration"]
outcome:
  metric_id: retention_90d
  definition: "Share of customers still active 90 days after acquisition"
  value_type: ratio
  numerator: retained_90d
  denominator: customer_id
time:
  observation_start: "2025-01-01T00:00:00+00:00"
  observation_end: "2025-06-30T00:00:00+00:00"
data:
  entity_column: customer_id
  event_time_column: acquisition_date
  treatment_column: campaign_exposed
  outcome_column: retained_90d
  covariate_columns: ["acquisition_channel"]
  observation_window_days: 90
  analysis_end: "2025-06-30T00:00:00+00:00"
causal:
  treatment: campaign_exposed
  outcome: retained_90d
  population: "Customers in the built-in demonstration"
  estimand: "Average treatment effect of campaign exposure on 90-day retention"
  strategy: regression_adjustment
  adjustment_set: ["acquisition_channel"]
  assumptions:
    - "Exposure is recorded without error."
    - "Retention is measured identically for both groups."
  falsification_checks: []
  sensitivity_checks: []
claims:
  - text: "Exposed customers had higher observed 90-day retention than unexposed customers."
    claim_class: descriptive
  - text: "The campaign caused higher 90-day retention."
    claim_class: causal
'''


def run_demo(name: str, output_directory: Path) -> tuple[DemoCase, AssessmentRun]:
    case = CASES[name]
    input_directory = output_directory / "input"
    input_directory.mkdir(parents=True, exist_ok=True)
    data_path = input_directory / "customers.csv"
    question_path = input_directory / "question.yaml"
    data_path.write_text(case.csv, encoding="utf-8")
    question_path.write_text(_question_yaml(case), encoding="utf-8")
    run = AssessmentRunner().run(
        data_sources=(data_path,),
        spec=load_spec(question_path),
        output_directory=output_directory,
    )
    return case, run
