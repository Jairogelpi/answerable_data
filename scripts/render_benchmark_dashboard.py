"""Render mutation_report.json as a static SVG dashboard card.

No plotting library: the layout is fixed (a title, three headline numbers,
four action bars), so hand-built SVG text/rect elements are shorter and more
auditable than pulling in a charting dependency for one image.

Usage:
    answerable benchmark mutations --output runs/emt
    python scripts/render_benchmark_dashboard.py runs/emt/mutation_report.json \\
        --output benchmarks/releases/emt-v1/dashboard.svg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_WIDTH = 640
_BAR_ORDER = ("KEEP", "QUALIFY", "RETRACT", "REVERSE")
_BAR_X = 190
_BAR_MAX_WIDTH = 380

# Light/dark tokens via prefers-color-scheme; GitHub's SVG sanitizer allows
# an inline <style> with a media query, so the badge matches the viewer's
# theme instead of committing to one background.
_STYLE = """
  :root { --bg:#ffffff; --card:#f6f8fa; --border:#d0d7de; --fg:#1f2328;
          --muted:#57606a; --accent:#1a7f37; --track:#d0d7de; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --fg:#e6edf3;
            --muted:#8b949e; --accent:#3fb950; --track:#30363d; }
  }
  .bg { fill: var(--bg); }
  .card { fill: var(--card); stroke: var(--border); }
  .title { fill: var(--fg); font: 700 20px system-ui, sans-serif; }
  .subtitle { fill: var(--muted); font: 400 13px system-ui, sans-serif; }
  .headline { fill: var(--accent); font: 700 34px system-ui, sans-serif; }
  .headline-label { fill: var(--muted); font: 400 12px system-ui, sans-serif; }
  .stat-value { fill: var(--fg); font: 700 15px system-ui, sans-serif; }
  .stat-label { fill: var(--muted); font: 400 12px system-ui, sans-serif; }
  .bar-label { fill: var(--fg); font: 600 13px system-ui, sans-serif; }
  .bar-pct { fill: var(--muted); font: 400 12px system-ui, sans-serif; }
  .track { fill: var(--track); }
  .fill { fill: var(--accent); }
  .footer { fill: var(--muted); font: 400 11px system-ui, sans-serif; }
""".strip()


def render(report: dict[str, object]) -> str:
    total = int(report["total_pairs"])  # type: ignore[arg-type]
    passed = round(float(report["action_accuracy"]) * total)  # type: ignore[arg-type]
    unsafe = float(report["unsafe_keep_rate"])  # type: ignore[arg-type]
    overreaction = float(report["overreaction_rate"])  # type: ignore[arg-type]
    repro_hash = str(report["reproducibility_hash"])[:12]
    release_pass = bool(report["release_pass"])
    recall = {
        "KEEP": 1.0 - overreaction,
        "QUALIFY": float(report["qualify_recall"]),  # type: ignore[arg-type]
        "RETRACT": float(report["retract_recall"]),  # type: ignore[arg-type]
        "REVERSE": float(report["reverse_recall"]),  # type: ignore[arg-type]
    }

    height = 300 + len(_BAR_ORDER) * 34
    bars = []
    for index, action in enumerate(_BAR_ORDER):
        y = 236 + index * 34
        pct = recall[action]
        fill_width = round(_BAR_MAX_WIDTH * pct)
        bars.append(
            f'<text x="24" y="{y + 14}" class="bar-label">{action}</text>'
            f'<rect x="{_BAR_X}" y="{y}" width="{_BAR_MAX_WIDTH}" height="16" rx="3" class="track"/>'
            f'<rect x="{_BAR_X}" y="{y}" width="{fill_width}" height="16" rx="3" class="fill"/>'
            f'<text x="{_BAR_X + _BAR_MAX_WIDTH + 10}" y="{y + 13}" class="bar-pct">{pct:.0%}</text>'
        )

    gate_label = "RELEASE GATE: PASS" if release_pass else "RELEASE GATE: FAIL"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}" role="img" aria-label="AnswerableBench Epistemic Mutation Testing results">
  <title>AnswerableBench — Epistemic Mutation Testing</title>
  <style>{_STYLE}</style>
  <rect class="bg" width="{_WIDTH}" height="{height}"/>
  <rect class="card" x="1" y="1" width="{_WIDTH - 2}" height="{height - 2}" rx="10"/>
  <text x="24" y="40" class="title">ANSWERABLEBENCH</text>
  <text x="24" y="60" class="subtitle">Can an analytical system change its mind when evidence changes?</text>

  <text x="24" y="118" class="headline">{passed} / {total}</text>
  <text x="24" y="136" class="headline-label">mutations passed</text>

  <text x="220" y="112" class="stat-value">{unsafe:.0%}</text>
  <text x="220" y="130" class="stat-label">Unsafe KEEP</text>

  <text x="380" y="112" class="stat-value">{overreaction:.0%}</text>
  <text x="380" y="130" class="stat-label">Overreaction</text>

  <text x="540" y="112" class="stat-value">{repro_hash}</text>
  <text x="540" y="130" class="stat-label">Reproducibility hash</text>

  <line x1="24" y1="160" x2="{_WIDTH - 24}" y2="160" stroke="var(--border)"/>
  <text x="24" y="185" class="bar-label">Recall by action</text>
  {"".join(bars)}

  <text x="24" y="{height - 18}" class="footer">{gate_label} · emt-v1 · {total} paired mutation tests</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a mutation_report.json as an SVG card.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(report), encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
