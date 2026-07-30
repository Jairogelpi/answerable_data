from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from answerable.quality.models import Finding, Severity


@dataclass(frozen=True, slots=True)
class PredictiveAssessment:
    brier_score: float
    baseline_brier: float
    findings: tuple[Finding, ...]


class PredictiveAssessor:
    def assess(
        self,
        probabilities: tuple[float, ...],
        labels: tuple[int, ...],
        *,
        baseline_probability: float,
        train_end: datetime,
        validation_start: datetime,
        test_start: datetime,
        prediction_times: tuple[datetime, ...] = (),
        feature_available_times: tuple[datetime, ...] = (),
        subgroup_sizes: tuple[int, ...] = (),
        drift_score: float = 0.0,
        labels_complete: bool = True,
    ) -> PredictiveAssessment:
        if not probabilities or len(probabilities) != len(labels):
            raise ValueError("probabilities and labels must be non-empty and aligned")
        if any(not 0 <= value <= 1 for value in probabilities) or any(
            value not in (0, 1) for value in labels
        ):
            raise ValueError("invalid probability or binary label")
        findings: list[Finding] = []
        if not train_end < validation_start < test_start:
            findings.append(
                Finding(
                    "split_leakage",
                    Severity.BLOCKER,
                    "Train, validation, and test periods are not strictly separated.",
                )
            )
        if prediction_times or feature_available_times:
            if len(prediction_times) != len(feature_available_times):
                raise ValueError("prediction and feature-availability times must align")
            if any(
                feature > prediction
                for prediction, feature in zip(
                    prediction_times, feature_available_times, strict=True
                )
            ):
                findings.append(
                    Finding(
                        "feature_leakage",
                        Severity.BLOCKER,
                        "A feature was unavailable at prediction time.",
                    )
                )
        brier = sum(
            (probability - label) ** 2
            for probability, label in zip(probabilities, labels, strict=True)
        ) / len(labels)
        baseline = sum((baseline_probability - label) ** 2 for label in labels) / len(labels)
        if brier >= baseline:
            findings.append(
                Finding(
                    "baseline_not_beaten",
                    Severity.BLOCKER,
                    "The model does not improve on the declared baseline.",
                )
            )
        observed_rate = sum(labels) / len(labels)
        if abs(sum(probabilities) / len(probabilities) - observed_rate) > 0.1:
            findings.append(
                Finding(
                    "miscalibration",
                    Severity.BLOCKER,
                    "Predicted probabilities are not calibrated to observed outcomes.",
                )
            )
        if subgroup_sizes and min(subgroup_sizes) < 30:
            findings.append(
                Finding(
                    "unreliable_subgroup",
                    Severity.WARNING,
                    "At least one subgroup is below the reliability threshold.",
                )
            )
        if drift_score > 0.2:
            findings.append(
                Finding("drift", Severity.WARNING, "Input drift exceeds the declared threshold.")
            )
        if not labels_complete:
            findings.append(
                Finding(
                    "delayed_labels",
                    Severity.BLOCKER,
                    "Evaluation labels are incomplete at the assessment cutoff.",
                )
            )
        return PredictiveAssessment(brier, baseline, tuple(findings))
