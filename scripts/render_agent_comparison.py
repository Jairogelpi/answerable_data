"""Render results.json (from build_emt_results.py) as an SVG comparison card.

Same hand-built-SVG approach as render_benchmark_dashboard.py, for the same
reason: a fixed bar-chart layout doesn't earn a charting dependency.

Usage:
    python scripts/render_agent_comparison.py runs/emt-results/results.json \\
        --output benchmarks/epistemic_mutations/results/2026-08-17-claude-codex/comparison.svg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_WIDTH = 640
_BAR_X = 140
_BAR_MAX_WIDTH = 380
_AGENT_ORDER = ("answerable", "codex", "claude", "gemini")

_STYLE = """
  :root { --bg:#ffffff; --card:#f6f8fa; --border:#d0d7de; --fg:#1f2328;
          --muted:#57606a; --accent:#1a7f37; --warn:#9a6700; --track:#d0d7de; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --fg:#e6edf3;
            --muted:#8b949e; --accent:#3fb950; --warn:#d29922; --track:#30363d; }
  }
  .bg { fill: var(--bg); }
  .card { fill: var(--card); stroke: var(--border); }
  .title { fill: var(--fg); font: 700 20px system-ui, sans-serif; }
  .subtitle { fill: var(--muted); font: 400 13px system-ui, sans-serif; }
  .section { fill: var(--fg); font: 600 13px system-ui, sans-serif; }
  .bar-label { fill: var(--fg); font: 600 13px system-ui, sans-serif; }
  .bar-pct { fill: var(--muted); font: 400 12px system-ui, sans-serif; }
  .track { fill: var(--track); }
  .fill-ok { fill: var(--accent); }
  .fill-warn { fill: var(--warn); }
  .footer { fill: var(--muted); font: 400 11px system-ui, sans-serif; }
""".strip()


def _bar(y: int, label: str, pct: float, ok: bool) -> str:
    fill_width = round(_BAR_MAX_WIDTH * pct)
    fill_class = "fill-ok" if ok else "fill-warn"
    return (
        f'<text x="24" y="{y + 14}" class="bar-label">{label}</text>'
        f'<rect x="{_BAR_X}" y="{y}" width="{_BAR_MAX_WIDTH}" height="16" rx="3" class="track"/>'
        f'<rect x="{_BAR_X}" y="{y}" width="{fill_width}" height="16" rx="3" class="{fill_class}"/>'
        f'<text x="{_BAR_X + _BAR_MAX_WIDTH + 10}" y="{y + 13}" class="bar-pct">{pct:.0%}</text>'
    )


def render(results: dict[str, object]) -> str:
    agents_data = results["agents"]  # type: ignore[assignment]
    invalidation = {
        row["agent_id"]: row  # type: ignore[index]
        for row in results["evidence_invalidation_analysis"]  # type: ignore[union-attr]
    }
    present = [a for a in _AGENT_ORDER if a in agents_data]  # type: ignore[operator]

    y = 130
    bars: list[str] = []
    bars.append('<text x="24" y="112" class="section">Overall accuracy</text>')
    for agent_id in present:
        acc = agents_data[agent_id]["accuracy"]  # type: ignore[index]
        bars.append(_bar(y, agent_id, acc, True))
        y += 30

    y += 20
    bars.append(
        f'<text x="24" y="{y - 6}" class="section">RETRACT rate on evidence invalidation'
        f" (should be 100%)</text>"
    )
    y += 12
    for agent_id in present:
        row = invalidation.get(agent_id)
        if not row or row["n"] == 0:  # type: ignore[index]
            continue
        rate = row["retract_correct"] / row["n"]  # type: ignore[index]
        bars.append(_bar(y, agent_id, rate, rate >= 0.95))
        y += 30

    height = y + 50
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height}" viewBox="0 0 {_WIDTH} {height}" role="img" aria-label="Answerable vs LLM agents on AnswerableBench EMT">
  <title>AnswerableBench EMT — Answerable vs LLM agents</title>
  <style>{_STYLE}</style>
  <rect class="bg" width="{_WIDTH}" height="{height}"/>
  <rect class="card" x="1" y="1" width="{_WIDTH - 2}" height="{height - 2}" rx="10"/>
  <text x="24" y="40" class="title">ANSWERABLE vs LLM AGENTS</text>
  <text x="24" y="60" class="subtitle">Same 48 frozen cases, same scorer, real CLI/API calls — not simulated</text>
  <line x1="24" y1="78" x2="{_WIDTH - 24}" y2="78" stroke="var(--border)"/>
  {"".join(bars)}
  <text x="24" y="{height - 18}" class="footer">emt-v1 · full run: benchmarks/epistemic_mutations/results/</text>
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render results.json as an SVG comparison card.")
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    results = json.loads(args.results.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(results), encoding="utf-8", newline="\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
