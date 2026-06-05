import pytest

from src.schemas import DEFAULT_ACTOR_ID, ScoreInput, SchemaValidationError


def payload(**overrides):
    base = {
        "metadata": {
            "session_id": "S001",
            "user_id": "U001",
            "scene_name": "会议室",
            "timestamp": "2026-06-06T10:00:00",
        },
        "dialogue_event": {
            "event_id": "EV_001",
            "game_id": "G001",
            "round_id": 1,
            "npc_role": "熊老板",
            "trigger_condition": {"time_pressure_level": 8},
            "npc_dialogue_script": "今天必须上线。",
            "user_response_type": "FreeText",
        },
        "response_meta": {
            "event_id": "EV_001",
            "user_free_text_input": "我会确认关键风险。",
            "user_selected_option": None,
            "response_time_ms": 10000,
        },
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def test_missing_event_id_fails():
    data = payload()
    del data["dialogue_event"]["event_id"]

    with pytest.raises(SchemaValidationError):
        ScoreInput.from_dict(data)


def test_round_id_must_be_integer():
    data = payload()
    data["dialogue_event"]["round_id"] = "abc"

    with pytest.raises(SchemaValidationError):
        ScoreInput.from_dict(data)


def test_option_without_text_is_valid():
    data = payload()
    data["dialogue_event"]["user_response_type"] = "Option"
    data["response_meta"]["user_free_text_input"] = None
    data["response_meta"]["user_selected_option"] = 2

    score_input = ScoreInput.from_dict(data)

    assert score_input.response_meta.user_selected_option == 2


def test_metadata_is_optional_and_separate_from_m_fields():
    data = payload()
    del data["metadata"]

    score_input = ScoreInput.from_dict(data)

    assert score_input.metadata.to_dict() == {}
    assert not hasattr(score_input.dialogue_event, "session_id")
    assert DEFAULT_ACTOR_ID == "玩家"


def test_user_response_type_enum_validation():
    data = payload()
    data["dialogue_event"]["user_response_type"] = "Voice"

    with pytest.raises(SchemaValidationError):
        ScoreInput.from_dict(data)

