from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from render_agent_comparison import render


def _results(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "agents": {
            "answerable": {
                "accuracy": 1.0,
                "unsafe_keep_rate": 0.0,
                "overreaction_rate": 0.0,
                "consistency": 1.0,
            },
            "claude": {
                "accuracy": 0.771,
                "unsafe_keep_rate": 0.0,
                "overreaction_rate": 0.0,
                "consistency": 0.958,
            },
        },
        "evidence_invalidation_analysis": [
            {
                "agent_id": "answerable",
                "n": 24,
                "retract_correct": 24,
                "wrong_by_action": {},
                "dominant_wrong_action": None,
                "dominant_wrong_count": 0,
                "wrong_total": 0,
                "p_value_dominant_direction": None,
            },
            {
                "agent_id": "claude",
                "n": 24,
                "retract_correct": 2,
                "wrong_by_action": {"QUALIFY": 22},
                "dominant_wrong_action": "QUALIFY",
                "dominant_wrong_count": 22,
                "wrong_total": 22,
                "p_value_dominant_direction": 3.19e-11,
            },
        ],
    }
    base.update(overrides)
    return base


def test_render_is_valid_xml_and_embeds_agent_labels() -> None:
    svg = render(_results())

    root = ElementTree.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "answerable" in svg
    assert "claude" in svg
    assert "77%" in svg  # claude accuracy
    assert "100%" in svg  # answerable accuracy / retract rate


def test_render_skips_agents_with_no_evidence_invalidation_cases() -> None:
    results = _results()
    results["evidence_invalidation_analysis"].append(  # type: ignore[union-attr]
        {"agent_id": "empty", "n": 0}
    )
    results["agents"]["empty"] = {  # type: ignore[index]
        "accuracy": 0.5,
        "unsafe_keep_rate": 0.0,
        "overreaction_rate": 0.0,
        "consistency": 1.0,
    }

    svg = render(results)  # must not raise ZeroDivisionError
    assert "<svg" in svg
