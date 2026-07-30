from __future__ import annotations

import unittest

from answerable.analysis.metrics import (
    MetricDefinition,
    MetricReconciler,
    MetricType,
)


class MetricSemanticsTests(unittest.TestCase):
    def test_FR_GRAIN_005_additive_metric_reconciles_within_tolerance(self) -> None:
        metric = MetricDefinition(
            metric_id="revenue",
            metric_type=MetricType.ADDITIVE,
            grain=("order_line",),
            expression="sum(net_revenue)",
        )
        result = MetricReconciler().reconcile(metric, before=100.0, after=100.00001)
        self.assertTrue(result.reconciled)
        self.assertFalse(result.blocked)

    def test_FR_GRAIN_005_metric_drift_creates_blocker(self) -> None:
        metric = MetricDefinition(
            metric_id="revenue",
            metric_type=MetricType.ADDITIVE,
            grain=("order_line",),
            expression="sum(net_revenue)",
        )
        result = MetricReconciler(relative_tolerance=1e-6).reconcile(
            metric, before=100.0, after=200.0
        )
        self.assertFalse(result.reconciled)
        self.assertTrue(result.blocked)
        self.assertEqual(result.relative_difference, 1.0)

    def test_phase_5_ratio_requires_numerator_and_denominator(self) -> None:
        with self.assertRaisesRegex(ValueError, "numerator"):
            MetricDefinition(
                metric_id="conversion",
                metric_type=MetricType.RATIO,
                grain=("visitor",),
                expression="converted / eligible",
            )

    def test_phase_5_metric_and_tolerance_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "required"):
            MetricDefinition("", MetricType.ADDITIVE, (), "")
        with self.assertRaisesRegex(ValueError, "negative"):
            MetricReconciler(relative_tolerance=-1)

    def test_FR_GRAIN_005_zero_baseline_is_explicit(self) -> None:
        metric = MetricDefinition(
            metric_id="revenue",
            metric_type=MetricType.ADDITIVE,
            grain=("order",),
            expression="sum(revenue)",
        )
        unchanged = MetricReconciler().reconcile(metric, before=0, after=0)
        changed = MetricReconciler().reconcile(metric, before=0, after=1)
        self.assertEqual(unchanged.relative_difference, 0)
        self.assertTrue(unchanged.reconciled)
        self.assertEqual(changed.relative_difference, float("inf"))
        self.assertTrue(changed.blocked)


if __name__ == "__main__":
    unittest.main()
