from __future__ import annotations

import unittest

from answerable.quality import DataQualityAssessor, QualityContext, ReferentialSource, Severity

FR_QUALITY_001 = "FR-QUALITY-001"
FR_QUALITY_002 = "FR-QUALITY-002"
FR_QUALITY_003 = "FR-QUALITY-003"
FR_QUALITY_004 = "FR-QUALITY-004"
FR_MISSING_001 = "FR-MISSING-001"
FR_MISSING_002 = "FR-MISSING-002"
FR_MISSING_003 = "FR-MISSING-003"


class DataQualityTests(unittest.TestCase):
    def test_phase_9_makes_severity_relative_to_required_fields(self) -> None:
        rows = (
            {"id": 1, "revenue": 10, "note": None},
            {"id": 2, "revenue": None, "note": "ok"},
        )
        findings = DataQualityAssessor().assess(
            rows,
            context=QualityContext(required_columns=frozenset({"revenue"})),
        )
        severity = {
            finding.affected_columns[0]: finding.severity
            for finding in findings
            if finding.code == "missing_values"
        }
        self.assertEqual(severity["revenue"], Severity.BLOCKER)
        self.assertEqual(severity["note"], Severity.WARNING)

    def test_phase_9_detects_schema_keys_references_units_and_truncation(self) -> None:
        rows = (
            {"id": 1, "customer": "missing", "amount": 10, "unit": "USD"},
            {"id": 1, "customer": "known", "amount": 20, "unit": "EUR"},
        )
        findings = DataQualityAssessor().assess(
            rows,
            context=QualityContext(
                required_columns=frozenset({"customer", "amount"}),
                key_columns=("id",),
                unit_column="unit",
            ),
            expected_columns=frozenset({"id", "customer", "amount", "unit", "date"}),
            references=(ReferentialSource("customer", frozenset({"known"})),),
            truncated=True,
        )
        codes = {finding.code for finding in findings}
        self.assertEqual(
            codes,
            {
                "schema_drift",
                "duplicate_keys",
                "referential_integrity",
                "inconsistent_units",
                "truncated_input",
            },
        )

    def test_phase_9_profiles_missingness_by_group_without_claiming_causality(self) -> None:
        rows = (
            {"group": "a", "value": None},
            {"group": "a", "value": 1},
            {"group": "b", "value": 2},
        )
        rates = DataQualityAssessor.missingness_by_group(rows, field="value", group="group")
        self.assertEqual(rates, {"a": 0.5, "b": 0})
        finding = DataQualityAssessor.missingness_mechanism_hypotheses(
            varies_by_observed_group=True, domain_reason_for_missingness=False
        )[0]
        self.assertTrue(finding.hypothesis_only)
        self.assertIn("MAR", finding.message)
        mnar = DataQualityAssessor.missingness_mechanism_hypotheses(
            varies_by_observed_group=False, domain_reason_for_missingness=True
        )[0]
        mcar = DataQualityAssessor.missingness_mechanism_hypotheses(
            varies_by_observed_group=False, domain_reason_for_missingness=False
        )[0]
        self.assertIn("MNAR", mnar.message)
        self.assertIn("MCAR", mcar.message)

    def test_phase_9_clean_data_produces_no_findings(self) -> None:
        rows = ({"id": 1, "value": 2}, {"id": 2, "value": 3})
        findings = DataQualityAssessor().assess(
            rows,
            context=QualityContext(key_columns=("id",)),
            expected_columns=frozenset({"id", "value"}),
        )
        self.assertEqual(findings, ())


if __name__ == "__main__":
    unittest.main()
