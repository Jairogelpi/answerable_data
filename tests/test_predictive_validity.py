from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from answerable.decision import PredictiveAssessor

FR_PREDICT_001 = "FR-PREDICT-001"
FR_PREDICT_002 = "FR-PREDICT-002"
FR_PREDICT_003 = "FR-PREDICT-003"
FR_PREDICT_004 = "FR-PREDICT-004"


class PredictiveValidityTests(unittest.TestCase):
    def test_phase_12_valid_model_beats_baseline_and_is_calibrated(self) -> None:
        assessment = PredictiveAssessor().assess(
            (0.1, 0.9, 0.2, 0.8),
            (0, 1, 0, 1),
            baseline_probability=0.5,
            train_end=datetime(2025, 1, 1, tzinfo=UTC),
            validation_start=datetime(2025, 2, 1, tzinfo=UTC),
            test_start=datetime(2025, 3, 1, tzinfo=UTC),
        )
        self.assertLess(assessment.brier_score, assessment.baseline_brier)
        self.assertEqual(assessment.findings, ())

    def test_phase_12_detects_temporal_feature_leakage_and_model_failures(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=UTC)
        assessment = PredictiveAssessor().assess(
            (0.9, 0.9),
            (0, 0),
            baseline_probability=0,
            train_end=now,
            validation_start=now,
            test_start=now,
            prediction_times=(now, now),
            feature_available_times=(now + timedelta(days=1), now),
            subgroup_sizes=(10, 100),
            drift_score=0.3,
            labels_complete=False,
        )
        self.assertEqual(
            {item.code for item in assessment.findings},
            {
                "split_leakage",
                "feature_leakage",
                "baseline_not_beaten",
                "miscalibration",
                "unreliable_subgroup",
                "drift",
                "delayed_labels",
            },
        )

    def test_phase_12_rejects_invalid_prediction_contract(self) -> None:
        now = datetime(2025, 1, 1, tzinfo=UTC)
        with self.assertRaises(ValueError):
            PredictiveAssessor().assess(
                (),
                (),
                baseline_probability=0.5,
                train_end=now,
                validation_start=now,
                test_start=now,
            )
        with self.assertRaises(ValueError):
            PredictiveAssessor().assess(
                (2,),
                (1,),
                baseline_probability=0.5,
                train_end=now,
                validation_start=now,
                test_start=now,
            )


if __name__ == "__main__":
    unittest.main()
