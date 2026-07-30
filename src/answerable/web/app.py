from __future__ import annotations

import html
from dataclasses import dataclass
from enum import StrEnum


class Screen(StrEnum):
    WORKSPACE = "workspace"
    SOURCES = "sources"
    NEW_ASSESSMENT = "new_assessment"
    FRAMING = "framing"
    MAPPING = "mapping"
    PROFILING = "profiling"
    PLAN_APPROVAL = "plan_approval"
    EXECUTION = "execution"
    EVIDENCE_GRAPH = "evidence_graph"
    CLAIM_INSPECTOR = "claim_inspector"
    REPAIR_PLAN = "repair_plan"
    WARRANT_REVIEW = "warrant_review"
    WARRANT_HISTORY = "warrant_history"
    POLICIES = "policies"
    BENCHMARKS = "benchmarks"


@dataclass(frozen=True, slots=True)
class ResultView:
    verdict: str
    explanation: str
    allowed_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    blockers: tuple[str, ...]
    assumptions: tuple[str, ...] = ()


class WebApplication:
    def render_result(self, view: ResultView) -> str:
        def items(values: tuple[str, ...], label: str) -> str:
            title = label.replace("-", " ").title()
            return (
                f'<section aria-labelledby="{label}"><h2 id="{label}">{title}</h2><ul>'
                + "".join(f"<li>{html.escape(value)}</li>" for value in values)
                + "</ul></section>"
            )

        return (
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            "<title>Answerable result</title></head><body>"
            '<a href="#result" class="skip-link">Skip to result</a><main id="result" tabindex="-1">'
            f'<h1>Verdict: <span data-status="{html.escape(view.verdict)}">'
            f"{html.escape(view.verdict)}</span></h1>"
            f'<p id="executive-explanation">{html.escape(view.explanation)}</p>'
            + items(view.allowed_claims, "allowed-claims")
            + items(view.forbidden_claims, "forbidden-claims")
            + items(view.blockers, "blockers")
            + items(view.assumptions, "assumptions")
            + '<details><summary>Complete provenance</summary><div role="tree" '
            'aria-label="Evidence provenance"></div></details>' + "</main></body></html>"
        )

    @staticmethod
    def navigation() -> tuple[Screen, ...]:
        return tuple(Screen)
