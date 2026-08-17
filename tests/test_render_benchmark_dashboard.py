from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from render_benchmark_dashboard import render


def _report(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "total_pairs": 48,
        "action_accuracy": 1.0,
        "unsafe_keep_rate": 0.0,
        "overreaction_rate": 0.0,
        "qualify_recall": 1.0,
        "retract_recall": 1.0,
        "reverse_recall": 1.0,
        "reproducibility_hash": "a" * 64,
        "release_pass": True,
    }
    base.update(overrides)
    return base


def test_render_embeds_headline_numbers_and_hash() -> None:
    svg = render(_report())

    assert "<svg" in svg and "</svg>" in svg
    assert "48 / 48" in svg
    assert "0%" in svg  # unsafe keep rate
    assert "a" * 12 in svg  # truncated reproducibility hash
    assert "RELEASE GATE: PASS" in svg


def test_render_reports_failed_gate_and_partial_accuracy() -> None:
    svg = render(
        _report(
            action_accuracy=0.9,
            unsafe_keep_rate=0.1,
            release_pass=False,
        )
    )

    assert "43 / 48" in svg  # round(0.9 * 48)
    assert "RELEASE GATE: FAIL" in svg


def test_render_is_valid_xml() -> None:
    from xml.etree import ElementTree

    svg = render(_report())
    root = ElementTree.fromstring(svg)  # raises on malformed XML
    assert root.tag.endswith("svg")
