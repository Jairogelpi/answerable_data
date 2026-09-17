# Numerical claim verification

The runner recomputes means from the supplied CSV/Parquet file. A submitted
claim is supported only if its class is `descriptive`, its complete text equals
the canonical statement, and applicable blockers/lint checks permit it. There
is no caller-controlled `verified` flag in the question JSON. Extra prose is
not validated merely because part of a statement contains correct numbers.

Example for UCI Bike Sharing `days-ready.csv`:

```text
Observed means of "cnt" by "workingday" among supplied records (six decimals): "0"=4330.168831 (n=231); "1"=4584.820000 (n=500).
```

Column names and group labels use JSON string quoting, groups are sorted by
their string values, and numbers have exactly six decimal places. Verification
compares the complete generated text: this admits the rounded six-decimal
result, not arbitrary tolerances or alternative rounding. `n` counts non-null
numeric outcomes. Missing/non-numeric/non-finite outcomes or null groups block
support, rather than silently changing the denominator. The population is the
supplied records, without causal interpretation, automatic date filtering or
extrapolation. Prepare the desired scope upstream. One source is accepted;
multiple sources require an explicit upstream join.

In JSON results and warrant `data_quality_relevance`, `computed_mean_claim`
contains the arithmetic candidate and `claim_validation` records each submitted
claim's status. A computed candidate is not permission to publish: check the
allowed list and all blockers. `unverified_or_blocked` does not mean disproved.
Arbitrary prose (including correct prose) and causal estimates remain unverified.
The question verdict can be `ANSWERABLE` with no supported submitted claims.

## Windows retest

From the existing checkout, update the source and editable installation:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\answerable.exe assess --data datos\bikes\days-ready.csv --question datos\bikes\false-number.json --output runs\bikes-false-number-fixed
```

Expected: the 99999/1 statement appears only under unsupported claims, never
supported. Then create a canonical true candidate without overwriting the old
questions:

```powershell
@'
import json
from pathlib import Path
folder = Path("datos/bikes")
q = json.loads((folder / "descriptive.json").read_text(encoding="utf-8"))
q["question_id"] = "bikes_verified_means"
q["claims"] = [{"claim_class": "descriptive", "text": 'Observed means of "cnt" by "workingday" among supplied records (six decimals): "0"=4330.168831 (n=231); "1"=4584.820000 (n=500).'}]
(folder / "verified-means.json").write_text(json.dumps(q, indent=2), encoding="utf-8")
'@ | .\.venv\Scripts\python.exe -
.\.venv\Scripts\answerable.exe assess --data datos\bikes\days-ready.csv --question datos\bikes\verified-means.json --output runs\bikes-verified-means
```

To run all six numerical regression cases automatically against the original file:

```powershell
.\.venv\Scripts\python.exe scripts\verify_bike_claims.py --data datos\bikes\day.csv --output runs\bikes-regression
```

Expected: `passed: 6`, with the true statement supported and all five altered
statements unsupported. The script independently computes reference means and
verifies each generated warrant. Dataset attribution: Hadi Fanaee-T (2013),
UCI Bike Sharing, DOI 10.24432/C5W894, CC BY 4.0.

Expected: that exact statement is supported. Change a value, group, count or
append another assertion: it must no longer be supported. Rerun duplicate-data
and warrant-tampering tests as before. Old warrants remain cryptographically
verifiable; a valid hash never retroactively proves a claim's truth. Regenerate
assessments created before this correction.
