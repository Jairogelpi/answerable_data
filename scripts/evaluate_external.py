"""External-data smoke evaluation; claim labels are authored, not independent review."""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import inspect
import json
import platform
from importlib.metadata import version
from pathlib import Path
from statistics import mean

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.spec_loader import load_spec

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "benchmarks/external"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(output: Path) -> list[dict[str, object]]:
    """Transform external dates without inventing observations; preserve every value."""
    manifest = json.loads((SUITE / "manifest.json").read_text())
    cases = []
    for source in manifest["sources"]:
        path = SUITE / source["path"]
        if digest(path) != source["sha256"]:
            raise ValueError(f"source hash mismatch: {path}")
        original = list(csv.DictReader(path.open(encoding="utf-8")))
        rows = []
        for row in original:
            if source["id"] == "flights":
                month = list(calendar.month_name).index(row["month"])
                day = f"{row['year']}-{month:02d}-01"
                value = float(row["passengers"])
            else:
                day = row["Date"]
                month = int(day[5:7])
                value = float(row["Temp"])
            rows.append(
                {
                    "entity": day,
                    "date": day + "T00:00:00+00:00",
                    "group": int(month > 6),
                    "value": value,
                }
            )
        for scope in ("full", "first_year"):
            selected = (
                rows
                if scope == "full"
                else [r for r in rows if r["entity"][:4] == rows[0]["entity"][:4]]
            )
            a = mean(r["value"] for r in selected if r["group"] == 0)
            b = mean(r["value"] for r in selected if r["group"] == 1)
            for variant in ("observed", "causal", "duplicate"):
                case_id = f"{source['id']}-{scope}-{variant}"
                folder = output / "cases" / case_id
                folder.mkdir(parents=True, exist_ok=True)
                data = [*selected, selected[0]] if variant == "duplicate" else selected
                with (folder / "data.csv").open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=["entity", "date", "group", "value"])
                    writer.writeheader()
                    writer.writerows(data)
                claim = (
                    f"Among these recorded {source['unit']}s, the observed mean was {a:.6g} "
                    f"in January-June and {b:.6g} in July-December ({source['units']})."
                )
                if variant == "causal":
                    claim = (
                        "Assignment to July-December caused the observed difference in outcomes."
                    )
                kind = "causal" if variant == "causal" else "descriptive"
                question = {
                    "question_id": case_id,
                    "raw_question": claim,
                    "normalized_question": claim,
                    "language": "en",
                    "analysis_type": kind,
                    "unit_of_analysis": source["unit"],
                    "population": {
                        "description": f"{source['id']} observations ({scope}); no extrapolation"
                    },
                    "outcome": {
                        "metric_id": "value",
                        "definition": source["units"],
                        "value_type": "continuous",
                    },
                    "time": {
                        "observation_start": selected[0]["date"],
                        "observation_end": "2000-01-01T00:00:00+00:00",
                    },
                    "data": {
                        "entity_column": "entity",
                        "event_time_column": "date",
                        "treatment_column": "group",
                        "outcome_column": "value",
                        "observation_window_days": 1,
                        "analysis_end": "2000-01-01T00:00:00+00:00",
                    },
                    "causal": {
                        "treatment": "group",
                        "outcome": "value",
                        "population": "recorded observations",
                        "estimand": "ATE",
                        "strategy": "regression_adjustment",
                    },
                    "claims": [{"text": claim, "claim_class": kind}],
                }
                (folder / "question.json").write_text(json.dumps(question, indent=2) + "\n")
                cases.append(
                    {
                        "case_id": case_id,
                        "source": source["id"],
                        "variant": variant,
                        "expected_allow": variant == "observed",
                        "claim": claim,
                        "data_sha256": digest(folder / "data.csv"),
                        "question_sha256": digest(folder / "question.json"),
                        "expected_means": {"0": a, "1": b},
                    }
                )
    return cases


def metrics(records: list[dict[str, object]]) -> dict[str, object]:
    valid = [r for r in records if r["expected_allow"]]
    invalid = [r for r in records if not r["expected_allow"]]
    false_blocks = sum(r["allowed"] is False for r in valid)
    unsafe = sum(r["allowed"] is True for r in invalid)
    return {
        "total": len(records),
        "valid_claims": len(valid),
        "invalid_claims": len(invalid),
        "false_blocks": false_blocks,
        "unsafe_allows": unsafe,
        "false_block_rate": false_blocks / len(valid) if valid else None,
        "unsafe_allow_rate": unsafe / len(invalid) if invalid else None,
        "release_false_blocks": sum(r.get("release_allowed") is False for r in valid),
        "errors": sum(r.get("error") is not None for r in records),
    }


def engine_fingerprint() -> str:
    root = Path(inspect.getfile(AssessmentRunner)).parents[1]
    entries = [(str(path.relative_to(root)), digest(path)) for path in sorted(root.rglob("*.py"))]
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def evaluate(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    cases = materialize(output)
    # Freeze labels and hashes before invoking the engine; the oracle is not a verdict lookup.
    (output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
    records = []
    for case in cases:
        folder = output / "cases" / str(case["case_id"])
        try:
            run = AssessmentRunner().run(
                data_sources=(folder / "data.csv",),
                spec=load_spec(folder / "question.json"),
                output_directory=folder / "assessment",
            )
            records.append(
                {
                    **case,
                    "allowed": case["claim"] in run.allowed_claims,
                    "verdict": run.verdict.value,
                    "release_allowed": case["claim"] in run.allowed_claims
                    and run.verdict.value in {"ANSWERABLE", "ANSWERABLE_WITH_ASSUMPTIONS"},
                    "blockers": [b.finding_id for b in run.blockers],
                    "observed_means": {
                        r["group"]: r["rate"] for r in run.observations["outcome_rates"]
                    },
                }
            )
        except Exception as error:
            records.append({**case, "allowed": None, "error": f"{type(error).__name__}: {error}"})
    report = {
        "protocol": "external-smoke-v1",
        "engine_sha256": engine_fingerprint(),
        "evaluator_sha256": digest(Path(__file__)),
        "dependencies": {name: version(name) for name in ("duckdb", "pyyaml", "sqlglot")},
        "python": platform.python_version(),
        "cases_sha256": digest(output / "cases.json"),
        "metrics": metrics(records),
        "limitations": [
            "Two external datasets; questions and labels authored within this project.",
            "Duplicate cases are explicit perturbations of external data.",
            "No population/causal generalization or independent expert validation.",
            "Cases within a source are correlated; no independence-based significance test.",
        ],
        "records": records,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.output)
    print(json.dumps(report["metrics"], indent=2))
    scores = report["metrics"]
    return int(bool(scores["false_blocks"] or scores["unsafe_allows"] or scores["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
