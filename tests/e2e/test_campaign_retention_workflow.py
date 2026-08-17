from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from answerable.application.assessment_runner import AssessmentRunner, load_warrant
from answerable.application.models import AssessmentRun
from answerable.application.spec_loader import load_spec
from answerable.cli import EXIT_BLOCKED, EXIT_INVALID_WARRANT, main
from answerable.domain.models import Verdict
from answerable.public import verify_warrant

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "campaign_retention"
ARTIFACTS = (
    "question_contract.json",
    "data_inventory.json",
    "check_plan.json",
    "findings.json",
    "evidence_graph.json",
    "verdict.json",
    "repair_plan.json",
    "warrant.json",
    "warrant.md",
)


def _run(output: Path, data: Path | None = None) -> AssessmentRun:
    return AssessmentRunner().run(
        data_sources=(data or EXAMPLE / "customers.csv",),
        spec=load_spec(EXAMPLE / "question.yaml"),
        output_directory=output,
    )


class CampaignRetentionWorkflowTest(unittest.TestCase):
    def test_golden_case_produces_every_artifact_and_blocks_causal_claims(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            run = _run(output)

            for name in ARTIFACTS:
                self.assertTrue((output / name).is_file(), name)
            self.assertEqual(run.verdict, Verdict.FUNDAMENTALLY_UNIDENTIFIABLE)
            self.assertEqual(
                {item.finding_id for item in run.blockers},
                {"immature_cohort", "positivity_violation", "causal_identification_failure"},
            )
            self.assertEqual(len(run.allowed_claims), 1)
            self.assertIn("Observed", run.allowed_claims[0])
            self.assertTrue(all("caused" in c or "led to" in c for c in run.forbidden_claims))
            self.assertAlmostEqual(float(str(run.observations["observed_difference"])), 0.12)
            self.assertTrue(verify_warrant(run.warrant))

            markdown = (output / "warrant.md").read_text(encoding="utf-8")
            self.assertIn("What you may not claim", markdown)
            self.assertIn("FUNDAMENTALLY_UNIDENTIFIABLE", markdown)

    def test_same_input_is_reproducible_and_changed_input_changes_the_warrant(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = _run(root / "a")
            second = _run(root / "b")
            self.assertEqual(first.assessment_id, second.assessment_id)
            self.assertEqual(first.warrant.content_hash, second.warrant.content_hash)

            source = EXAMPLE / "customers.csv"
            mutated = root / "mutated.csv"
            lines = source.read_text(encoding="utf-8").splitlines()
            lines[1] = lines[1].replace(",true", ",false")
            mutated.write_text("\n".join(lines) + "\n", encoding="utf-8")
            changed = _run(root / "c", data=mutated)
            self.assertNotEqual(first.warrant.content_hash, changed.warrant.content_hash)

    def test_cli_reports_blocked_verdict_and_verifies_the_written_warrant(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            stream = StringIO()
            with redirect_stdout(stream):
                code = main(
                    (
                        "--json",
                        "assess",
                        "--data",
                        str(EXAMPLE / "customers.csv"),
                        "--question",
                        str(EXAMPLE / "question.yaml"),
                        "--output",
                        str(output),
                        "--format",
                        "both",
                    )
                )
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, EXIT_BLOCKED)
            self.assertEqual(payload["verdict"], "FUNDAMENTALLY_UNIDENTIFIABLE")

            warrant = output / "warrant.json"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(("warrant", "verify", "--warrant", str(warrant))), 0)
            record = json.loads(warrant.read_text(encoding="utf-8"))
            record["canonical_json"] = record["canonical_json"].replace("current", "superseded")
            warrant.write_text(json.dumps(record), encoding="utf-8")
            self.assertFalse(verify_warrant(load_warrant(warrant)))
            with redirect_stdout(StringIO()):
                code = main(("warrant", "verify", "--warrant", str(warrant)))
            self.assertEqual(code, EXIT_INVALID_WARRANT)

    def test_format_flag_keeps_only_the_requested_surface(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, present, absent in (
                ("json", "warrant.json", "warrant.md"),
                ("markdown", "warrant.md", "warrant.json"),
            ):
                output = root / name
                with redirect_stdout(StringIO()):
                    main(
                        (
                            "assess",
                            "--data",
                            str(EXAMPLE / "customers.csv"),
                            "--question",
                            str(EXAMPLE / "question.yaml"),
                            "--output",
                            str(output),
                            "--format",
                            name,
                        )
                    )
                self.assertTrue((output / present).is_file(), present)
                self.assertFalse((output / absent).is_file(), absent)
