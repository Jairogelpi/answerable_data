from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from answerable.application.models import AssessmentRun


def _bullets(items: list[Any], empty: str) -> str:
    return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"


def render_markdown(run: AssessmentRun) -> str:
    """Plain-language warrant. Written for a reader who is not a statistician."""
    data: dict[str, Any] = dict(run.warrant.data)
    question = data["question"]
    outcome_rates: Any = run.observations.get("outcome_rates", [])
    rates = [
        f"{item['group']}: {item['rate']:.1%} of {item['entities']} {question['unit_of_analysis']}s"
        for item in outcome_rates
    ]
    repairs = data["minimum_evidence_plan"]["minimal"]
    sections = [
        "# Evidence Warrant",
        "",
        f"**Question:** {question['normalized_question']}",
        "",
        f"**Verdict:** `{run.verdict.value}`",
        "",
        data["executive_explanation"],
        "",
        "## What you may claim",
        "",
        _bullets(list(run.allowed_claims), "Nothing beyond the raw counts."),
        "",
        "## What you may not claim",
        "",
        _bullets(list(run.forbidden_claims), "No claim was rejected."),
        "",
        "## What the data shows",
        "",
        _bullets(rates, "No comparable groups were found."),
        "",
        "## Why the answer is blocked",
        "",
        _bullets(
            [f"**{item.finding_id}** — {item.message}" for item in run.blockers],
            "Nothing blocks this question.",
        ),
        "",
        "## What evidence is missing",
        "",
        (
            f"- {repairs['missing_information']}\n"
            f"- Why it matters: {repairs['why_it_matters']}\n"
            f"- How to get it: {repairs['collection_method']}"
            if repairs
            else "- Nothing; the evidence is complete."
        ),
        "",
        "## Provenance",
        "",
        _bullets(
            [
                f"`{item['path']}` — {item['rows']} rows — sha256 `{item['fingerprint'][:16]}…`"
                for item in data["provenance"]
            ],
            "No sources recorded.",
        ),
        "",
        f"Warrant `{run.warrant.warrant_id}` v{run.warrant.version}, "
        f"content hash `{run.warrant.content_hash}`.",
        "",
    ]
    return "\n".join(sections)
