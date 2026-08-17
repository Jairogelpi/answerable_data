from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_agent_tool_experiment import parse_action


def test_parse_action_prefers_the_explicit_action_line() -> None:
    text = "I ran the tool and it blocked the claim.\n\nACTION: RETRACT"
    assert parse_action(text) == "RETRACT"


def test_parse_action_is_case_insensitive_on_the_explicit_line() -> None:
    assert parse_action("some reasoning\naction: qualify") == "QUALIFY"


def test_parse_action_falls_back_to_any_action_word_without_the_marker() -> None:
    assert parse_action("Given this, I think we should REVERSE the conclusion.") == "REVERSE"


def test_parse_action_prefers_marked_line_over_an_earlier_stray_mention() -> None:
    # The reasoning mentions KEEP in passing while explaining why it doesn't
    # apply; only the marked line should decide the outcome.
    text = "This isn't a case for KEEP.\n\nACTION: RETRACT"
    assert parse_action(text) == "RETRACT"


def test_parse_action_returns_none_when_nothing_matches() -> None:
    assert parse_action("I couldn't determine an answer.") is None
