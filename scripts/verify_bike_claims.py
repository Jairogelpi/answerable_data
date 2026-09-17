"""Reproduce the user-reported UCI Bike Sharing claim bug on a local day.csv."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from statistics import mean

from answerable.application.assessment_runner import AssessmentRunner
from answerable.application.models import ClaimCandidate
from answerable.application.spec_loader import load_spec
from answerable.evidence.claims import ClaimClass
from answerable.public import verify_warrant


def run(data: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    with data.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 731, "Expected the original UCI day.csv (731 days)"
    groups = {g: [int(r["cnt"]) for r in rows if r["workingday"] == g] for g in ("0", "1")}
    assert [len(groups[g]) for g in ("0", "1")] == [231, 500]
    assert mean(groups["1"]) == 4584.82
    for row in rows:
        row["event_time"] = row["dteday"] + "T00:00:00+00:00"
    source = output / "days-ready.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    question = {
        "question_id": "bikes_numeric_regression",
        "raw_question": "Compare observed means in supplied days.",
        "normalized_question": "Compare observed means in supplied days.",
        "language": "en",
        "analysis_type": "descriptive",
        "unit_of_analysis": "day",
        "population": {"description": "731 supplied days; no extrapolation."},
        "outcome": {
            "metric_id": "rentals",
            "definition": "Recorded rentals",
            "value_type": "continuous",
        },
        "time": {
            "observation_start": "2011-01-01T00:00:00+00:00",
            "observation_end": "2013-01-02T00:00:00+00:00",
        },
        "data": {
            "entity_column": "instant",
            "event_time_column": "event_time",
            "treatment_column": "workingday",
            "outcome_column": "cnt",
            "observation_window_days": 1,
            "analysis_end": "2013-01-02T00:00:00+00:00",
        },
        "causal": {
            "treatment": "workingday",
            "outcome": "cnt",
            "population": "Recorded days",
            "estimand": "Observed difference",
            "strategy": "regression_adjustment",
        },
        "claims": [],
    }
    spec_path = output / "question.json"
    spec_path.write_text(json.dumps(question, indent=2), encoding="utf-8")
    spec = load_spec(spec_path)
    # Oracle uses Python statistics.mean, independently of DuckDB in the engine.
    good = (
        'Observed means of "cnt" by "workingday" among supplied records (six decimals): '
        f'"0"={mean(groups["0"]):.6f} (n=231); "1"={mean(groups["1"]):.6f} (n=500).'
    )
    cases = {
        "correct_means": (good, True),
        "reported_false_prose": (
            "Among recorded days, mean rentals were 99999 on working days "
            "and 1 on non-working days.",
            False,
        ),
        "false_number": (good.replace("4584.820000", "99999.000000"), False),
        "swapped_groups": (
            good.replace('"0"=', '"X"=').replace('"1"=', '"0"=').replace('"X"=', '"1"='),
            False,
        ),
        "wrong_count": (good.replace("n=500", "n=499"), False),
        "extra_causal_prose": (good + " Working days caused the increase.", False),
    }
    results = []
    for name, (text, expected) in cases.items():
        result = AssessmentRunner().run(
            data_sources=(source,),
            spec=replace(spec, claims=(ClaimCandidate(text, ClaimClass.DESCRIPTIVE),)),
            output_directory=output / name,
        )
        allowed = text in result.allowed_claims
        assert allowed == expected, name
        assert verify_warrant(result.warrant), name
        results.append({"case": name, "expected_supported": expected, "supported": allowed})
    report = {
        "source": "https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset",
        "source_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "rows": len(rows),
        "means": {g: mean(values) for g, values in groups.items()},
        "cases": results,
        "passed": len(results),
        "scope": "Numeric-claim regression, not full product or causal validation.",
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.output), indent=2))
