from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from answerable.quality.models import Finding, QualityContext, Severity


@dataclass(frozen=True, slots=True)
class ReferentialSource:
    column: str
    valid_values: frozenset[object]


class DataQualityAssessor:
    def assess(
        self,
        rows: tuple[dict[str, object], ...],
        *,
        context: QualityContext,
        expected_columns: frozenset[str] | None = None,
        references: tuple[ReferentialSource, ...] = (),
        truncated: bool = False,
    ) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        actual = frozenset(rows[0]) if rows else frozenset()
        if expected_columns is not None and actual != expected_columns:
            missing = expected_columns - actual
            severity = Severity.BLOCKER if missing & context.required_columns else Severity.WARNING
            findings.append(
                Finding(
                    "schema_drift",
                    severity,
                    "Observed columns differ from the expected schema.",
                    tuple(sorted(expected_columns ^ actual)),
                )
            )
        findings.extend(self._missingness(rows, context))
        findings.extend(self._duplicates(rows, context))
        findings.extend(self._references(rows, context, references))
        if context.unit_column and rows:
            units = {row.get(context.unit_column) for row in rows if row.get(context.unit_column)}
            if len(units) > 1:
                findings.append(
                    Finding(
                        "inconsistent_units",
                        Severity.BLOCKER,
                        "Multiple measurement units would make aggregation unsafe.",
                        (context.unit_column,),
                        len(units),
                    )
                )
        if truncated:
            findings.append(
                Finding(
                    "truncated_input",
                    Severity.BLOCKER,
                    "Input is truncated, so completeness-dependent results are unsafe.",
                )
            )
        return tuple(findings)

    @staticmethod
    def _missingness(
        rows: tuple[dict[str, object], ...], context: QualityContext
    ) -> Iterable[Finding]:
        if not rows:
            return ()
        findings: list[Finding] = []
        for column in sorted(rows[0]):
            count = sum(row.get(column) is None for row in rows)
            if count:
                severity = (
                    Severity.BLOCKER if column in context.required_columns else Severity.WARNING
                )
                findings.append(
                    Finding(
                        "missing_values",
                        severity,
                        f"{count} of {len(rows)} values are missing.",
                        (column,),
                        count / len(rows),
                    )
                )
        return findings

    @staticmethod
    def _duplicates(
        rows: tuple[dict[str, object], ...], context: QualityContext
    ) -> Iterable[Finding]:
        if not context.key_columns:
            return ()
        keys = [tuple(row.get(column) for column in context.key_columns) for row in rows]
        duplicates = sum(count - 1 for count in Counter(keys).values() if count > 1)
        if not duplicates:
            return ()
        return (
            Finding(
                "duplicate_keys",
                Severity.BLOCKER,
                "Declared entity keys are not unique.",
                context.key_columns,
                duplicates,
            ),
        )

    @staticmethod
    def _references(
        rows: tuple[dict[str, object], ...],
        context: QualityContext,
        references: tuple[ReferentialSource, ...],
    ) -> Iterable[Finding]:
        findings: list[Finding] = []
        for reference in references:
            missing = sum(
                row.get(reference.column) is not None
                and row.get(reference.column) not in reference.valid_values
                for row in rows
            )
            if missing:
                severity = (
                    Severity.BLOCKER
                    if reference.column in context.required_columns
                    else Severity.WARNING
                )
                findings.append(
                    Finding(
                        "referential_integrity",
                        severity,
                        "Values do not resolve against the reference population.",
                        (reference.column,),
                        missing,
                    )
                )
        return findings

    @staticmethod
    def missingness_by_group(
        rows: tuple[dict[str, object], ...], *, field: str, group: str
    ) -> dict[object, float]:
        totals: dict[object, int] = defaultdict(int)
        missing: dict[object, int] = defaultdict(int)
        for row in rows:
            key = row.get(group)
            totals[key] += 1
            missing[key] += row.get(field) is None
        return {key: missing[key] / total for key, total in totals.items()}

    @staticmethod
    def missingness_mechanism_hypotheses(
        *, varies_by_observed_group: bool, domain_reason_for_missingness: bool
    ) -> tuple[Finding, ...]:
        if domain_reason_for_missingness:
            message = "MNAR is plausible because missingness may depend on the unobserved value."
        elif varies_by_observed_group:
            message = "MAR is plausible because missingness varies with observed attributes."
        else:
            message = "MCAR remains plausible, but cannot be established from this check alone."
        return (
            Finding(
                "missingness_mechanism",
                Severity.INFO,
                message,
                hypothesis_only=True,
            ),
        )
