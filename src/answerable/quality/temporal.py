from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from answerable.quality.models import Finding, Severity


@dataclass(frozen=True, slots=True)
class TemporalContext:
    event_time: str
    prediction_time: str | None = None
    feature_available_time: str | None = None
    label_time: str | None = None
    observation_window: timedelta | None = None
    analysis_end: datetime | None = None
    require_timezone: bool = True


class TemporalAssessor:
    def assess(
        self, rows: tuple[dict[str, object], ...], *, context: TemporalContext
    ) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        times = [row.get(context.event_time) for row in rows]
        parsed = [value for value in times if isinstance(value, datetime)]
        if len(parsed) != len(times):
            findings.append(
                Finding(
                    "invalid_event_time",
                    Severity.BLOCKER,
                    "Every event requires a typed event timestamp.",
                    (context.event_time,),
                )
            )
            return tuple(findings)
        if context.require_timezone and any(value.tzinfo is None for value in parsed):
            findings.append(
                Finding(
                    "timezone_ambiguity",
                    Severity.BLOCKER,
                    "Timezone-naive timestamps cannot establish reliable ordering.",
                    (context.event_time,),
                )
            )
        if context.prediction_time and context.feature_available_time:
            leakage = 0
            for row in rows:
                prediction = row.get(context.prediction_time)
                available = row.get(context.feature_available_time)
                if (
                    isinstance(prediction, datetime)
                    and isinstance(available, datetime)
                    and available > prediction
                ):
                    leakage += 1
            if leakage:
                findings.append(
                    Finding(
                        "prediction_leakage",
                        Severity.BLOCKER,
                        "Features became available after prediction time.",
                        (context.feature_available_time, context.prediction_time),
                        leakage,
                    )
                )
        if context.analysis_end and context.observation_window:
            immature = sum(
                value + context.observation_window > context.analysis_end for value in parsed
            )
            if immature:
                findings.append(
                    Finding(
                        "immature_cohort",
                        Severity.BLOCKER,
                        "Some entities have not completed the observation window.",
                        (context.event_time,),
                        immature / len(parsed),
                    )
                )
        if context.label_time and context.analysis_end:
            delayed = 0
            for row in rows:
                label = row.get(context.label_time)
                if label is None or (isinstance(label, datetime) and label > context.analysis_end):
                    delayed += 1
            if delayed:
                findings.append(
                    Finding(
                        "right_censoring",
                        Severity.BLOCKER,
                        "Outcome labels are unavailable by the analysis cutoff.",
                        (context.label_time,),
                        delayed,
                    )
                )
        return tuple(findings)

    @staticmethod
    def definition_changes(
        versions: tuple[tuple[datetime, str], ...],
    ) -> tuple[Finding, ...]:
        definitions = {definition for _, definition in versions}
        if len(definitions) <= 1:
            return ()
        return (
            Finding(
                "definition_change",
                Severity.BLOCKER,
                "The metric definition changed inside the analysis period.",
                observed=len(definitions),
            ),
        )
