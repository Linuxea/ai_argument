"""Input-validation contract tests (Field length caps)."""

import pytest
from pydantic import ValidationError

from app.models import (
    CustomDebaterRequest,
    DebateConfig,
    Debater,
    RefineTopicRequest,
    UserMessage,
)


def test_debate_config_topic_length_capped():
    with pytest.raises(ValidationError):
        DebateConfig(topic="x" * 501, debater_names=["a", "b"])


def test_debate_config_debater_count_capped():
    # 21 names exceeds the MAX_DEBATERS (20) cap
    names = [f"d{i}" for i in range(21)]
    with pytest.raises(ValidationError):
        DebateConfig(topic="ok", debater_names=names)


def test_user_message_length_capped():
    with pytest.raises(ValidationError):
        UserMessage(message="x" * 2001)


def test_debater_avatar_length_capped():
    with pytest.raises(ValidationError):
        Debater(name="X", personality="p", avatar="😀" * 20)


def test_debater_personality_length_capped():
    with pytest.raises(ValidationError):
        Debater(name="X", personality="x" * 1001)


def test_custom_debater_request_name_length_capped():
    with pytest.raises(ValidationError):
        CustomDebaterRequest(name="x" * 51, personality="p")


def test_refine_topic_request_length_capped():
    with pytest.raises(ValidationError):
        RefineTopicRequest(topic="x" * 501)


def test_valid_inputs_within_caps_accepted():
    """Sanity check: typical inputs still pass validation."""
    Debater(name="分析家", personality="冷静分析。")
    DebateConfig(topic="AI 是否应取代教师？", debater_names=["正方", "反方"])
    UserMessage(message="我的观点是……")


def test_debater_name_rejects_brackets():
    with pytest.raises(ValidationError):
        Debater(name="evil[name]", personality="p")


def test_debater_name_rejects_angle_brackets():
    with pytest.raises(ValidationError):
        Debater(name="evil<name>", personality="p")


def test_debater_name_rejects_colon():
    with pytest.raises(ValidationError):
        Debater(name="evil:name", personality="p")


def test_debater_name_rejects_braces():
    with pytest.raises(ValidationError):
        Debater(name="evil{name}", personality="p")


def test_debater_name_rejects_newline():
    with pytest.raises(ValidationError):
        Debater(name="evil\nname", personality="p")


def test_debater_name_accepts_normal_names():
    Debater(name="张三分", personality="p")
    Debater(name="The Optimist", personality="p")
    Debater(name="abc-123_测试", personality="p")
