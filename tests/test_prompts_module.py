"""Tests for the app.prompts package (loader, defense, stances, builders)."""
from app.prompts.defense import (
    JUDGE_NOTE,
    TOPIC_CLOSE,
    TOPIC_NOTE,
    TOPIC_OPEN,
    USER_MSG_CLOSE,
    USER_MSG_NOTE,
    USER_MSG_OPEN,
)
from app.prompts.loader import load_prompt
from app.prompts.stances import STANCE_INSTRUCTIONS


def test_load_prompt_returns_content():
    text = load_prompt("debate_rules")
    assert isinstance(text, str)
    assert len(text) > 50
    assert "multi-party debate" in text


def test_load_prompt_missing_file_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist_xyz")


def test_defense_fences_are_xml_like():
    assert TOPIC_OPEN == "<topic>"
    assert TOPIC_CLOSE == "</topic>"
    assert USER_MSG_OPEN == "<user_message>"
    assert USER_MSG_CLOSE == "</user_message>"


def test_defense_notes_are_nonempty_strings():
    for note in (TOPIC_NOTE, USER_MSG_NOTE, JUDGE_NOTE):
        assert isinstance(note, str) and len(note) > 10
        assert "instructions" in note.lower() or "data" in note.lower()


def test_stance_instructions_has_all_three_keys():
    for stance in ("正方", "反方", "中立"):
        assert stance in STANCE_INSTRUCTIONS
        assert isinstance(STANCE_INSTRUCTIONS[stance], str)
        assert len(STANCE_INSTRUCTIONS[stance]) > 50
    assert set(STANCE_INSTRUCTIONS) == {"正方", "反方", "中立"}
