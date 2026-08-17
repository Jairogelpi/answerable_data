from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.models import DataMapping
from answerable.application.spec_loader import load_spec
from answerable.domain.models import Verdict

QUESTION = {
    "question_id": "q_clean",
    "raw_question": "Did exposure change 90-day retention?",
    "normalized_question": "Did exposure change 90-day retention for customers acquired in 2025?",
    "language": "en",
    "analysis_type": "causal",
    "unit_of_analysis": "customer",
    "population": {"description": "Customers acquired in January 2025"},
    "outcome": {
        "metric_id": "retention_90d",
        "definition": "Active 90 days after acquisition",
        "value_type": "ratio",
        "numerator": "retained_90d",
        "denominator": "customer_id",
    },
    "time": {
        "observation_start": "2025-01-01T00:00:00+00:00",
        "observation_end": "2025-06-30T00:00:00+00:00",
    },
    "data": {
        "entity_column": "customer_id",
        "event_time_column": "acquisition_date",
        "treatment_column": "campaign_exposed",
        "outcome_column": "retained_90d",
        "covariate_columns": ["acquisition_channel"],
        "observation_window_days": 90,
        "analysis_end": "2025-06-30T00:00:00+00:00",
    },
    "causal": {
        "treatment": "campaign_exposed",
        "outcome": "retained_90d",
        "population": "Customers acquired in January 2025",
        "estimand": "ATT of exposure on 90-day retention",
        "strategy": "regression_adjustment",
        "adjustment_set": ["acquisition_channel"],
        "sensitivity_checks": ["unmeasured confounding bound"],
    },
    "claims": [
        {"text": "Exposure caused higher 90-day retention.", "claim_class": "causal"},
    ],
}
HEADER = "customer_id,acquisition_date,acquisition_channel,campaign_exposed,retained_90d"


def _rows(timestamp: str, *, size: int = 8) -> str:
    # Tile the 8-row base pattern rather than extend it with more index
    # arithmetic: the exposed/retained cycle lengths (4 and 3) share a
    # period of 12, so a naively larger range washes the effect back
    # towards zero instead of just adding a bigger, equally powered sample.
    lines = [HEADER]
    for index in range(size):
        base = index % 8
        channel = "paid" if base % 2 else "organic"
        exposed = "true" if base % 4 < 2 else "false"
        retained = "true" if base % 3 else "false"
        lines.append(f"c{index},{timestamp},{channel},{exposed},{retained}")
    return "\n".join(lines) + "\n"


def _case(
    root: Path, timestamp: str, question: dict[str, object] | None = None, *, size: int = 8
) -> Path:
    (root / "customers.csv").write_text(_rows(timestamp, size=size), encoding="utf-8")
    (root / "question.json").write_text(json.dumps(question or QUESTION), encoding="utf-8")
    return root


class RunnerEdgeCaseTest(unittest.TestCase):
    def test_supported_design_opens_the_causal_gate(self) -> None:
        with TemporaryDirectory() as directory:
            # Every assessment now also runs a statistical-power check; a
            # "cleanly answerable" case has to actually be powered, not
            # just directionally correct on a handful of rows.
            root = _case(Path(directory), "2025-01-10T00:00:00+00:00", size=160)
            run = AssessmentRunner(signer="ci", secret=b"secret").run(
                data_sources=(root / "customers.csv",),
                spec=load_spec(root / "question.json"),
                output_directory=root / "out",
            )
            self.assertEqual(run.verdict, Verdict.ANSWERABLE)
            self.assertEqual(run.blockers, ())
            self.assertEqual(run.forbidden_claims, ())
            self.assertEqual(run.allowed_claims, ("Exposure caused higher 90-day retention.",))
            markdown = (root / "out" / "warrant.md").read_text(encoding="utf-8")
            self.assertIn("Nothing blocks this question.", markdown)
            self.assertIn("the evidence is complete", markdown)

    def test_timezone_naive_timestamps_are_a_data_integrity_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = _case(Path(directory), "2025-01-10 00:00:00")
            run = AssessmentRunner().run(
                data_sources=(root / "customers.csv",),
                spec=load_spec(root / "question.json"),
                output_directory=root / "out",
            )
            self.assertIn("timezone_ambiguity", {item.finding_id for item in run.blockers})

    def test_duplicate_entities_block_every_claim(self) -> None:
        with TemporaryDirectory() as directory:
            root = _case(Path(directory), "2025-01-10T00:00:00+00:00")
            source = root / "customers.csv"
            lines = source.read_text(encoding="utf-8").splitlines()
            source.write_text("\n".join([*lines, lines[1]]) + "\n", encoding="utf-8")
            run = AssessmentRunner().run(
                data_sources=(source,),
                spec=load_spec(root / "question.json"),
                output_directory=root / "out",
            )
            self.assertEqual(run.verdict, Verdict.DATA_INTEGRITY_FAILURE)

    def test_invalid_inputs_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _case(root, "2025-01-10T00:00:00+00:00")
            spec = load_spec(root / "question.json")
            with self.assertRaises(ValueError):
                AssessmentRunner().run(data_sources=(), spec=spec, output_directory=root / "out")

            naive = {**QUESTION["time"], "observation_start": "2025-01-01T00:00:00"}  # type: ignore[dict-item]
            (root / "naive.json").write_text(
                json.dumps({**QUESTION, "time": naive}), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_spec(root / "naive.json")

            (root / "list.yaml").write_text("- not a mapping\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_spec(root / "list.yaml")

        with self.assertRaises(ValueError):
            DataMapping(
                entity_column="a",
                event_time_column="b",
                treatment_column="c",
                outcome_column="d",
                observation_window_days=0,
                analysis_end=datetime.now(UTC),
            )
        with self.assertRaises(ValueError):
            DataMapping(
                entity_column="a",
                event_time_column="b",
                treatment_column="c",
                outcome_column="d",
                observation_window_days=90,
                analysis_end=datetime(2025, 1, 1),
            )
