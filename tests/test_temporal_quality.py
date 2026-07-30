from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from answerable.quality import Severity, TemporalAssessor, TemporalContext

FR_TIME_001 = "FR-TIME-001"
FR_TIME_002 = "FR-TIME-002"
FR_TIME_003 = "FR-TIME-003"
FR_TIME_004 = "FR-TIME-004"
FR_TIME_005 = "FR-TIME-005"


class TemporalQualityTests(unittest.TestCase):
    def test_phase_9_detects_leakage_immaturity_and_censoring(self) -> None:
        event = datetime(2026, 7, 20, tzinfo=UTC)
        cutoff = datetime(2026, 7, 30, tzinfo=UTC)
        rows = (
            {
                "event_at": event,
                "prediction_at": event,
                "available_at": event + timedelta(days=1),
                "label_at": None,
            },
        )
        findings = TemporalAssessor().assess(
            rows,
            context=TemporalContext(
                event_time="event_at",
                prediction_time="prediction_at",
                feature_available_time="available_at",
                label_time="label_at",
                observation_window=timedelta(days=30),
                analysis_end=cutoff,
            ),
        )
        self.assertEqual(
            {finding.code for finding in findings},
            {"prediction_leakage", "immature_cohort", "right_censoring"},
        )
        self.assertTrue(all(finding.severity is Severity.BLOCKER for finding in findings))

    def test_phase_9_blocks_timezone_ambiguity_and_invalid_event_time(self) -> None:
        naive = ({"event_at": datetime(2026, 1, 1)},)
        codes = {
            item.code
            for item in TemporalAssessor().assess(
                naive, context=TemporalContext(event_time="event_at")
            )
        }
        self.assertEqual(codes, {"timezone_ambiguity"})

        invalid = ({"event_at": "2026-01-01"},)
        finding = TemporalAssessor().assess(
            invalid, context=TemporalContext(event_time="event_at")
        )[0]
        self.assertEqual(finding.code, "invalid_event_time")

    def test_phase_9_detects_metric_definition_changes(self) -> None:
        versions = (
            (datetime(2026, 1, 1, tzinfo=UTC), "gross_revenue"),
            (datetime(2026, 2, 1, tzinfo=UTC), "net_revenue"),
        )
        finding = TemporalAssessor.definition_changes(versions)[0]
        self.assertEqual(finding.code, "definition_change")
        stable = TemporalAssessor.definition_changes((versions[0],))
        self.assertEqual(stable, ())


if __name__ == "__main__":
    unittest.main()
