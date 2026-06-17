import sys
from types import SimpleNamespace

from src.llm_scorer import parse_llm_json_result, score_with_llm
from src.schemas import ScoreInput


def make_input(text="我会先确认风险，再推动团队合作。"):
    return ScoreInput.from_dict(
        {
            "dialogue_event": {
                "event_id": "EV_001",
                "game_id": "G001",
                "round_id": 1,
                "npc_role": "熊老板",
                "trigger_condition": {},
                "npc_dialogue_script": "今天必须上线。",
                "user_response_type": "FreeText",
            },
            "response_meta": {
                "event_id": "EV_001",
                "user_free_text_input": text,
                "response_time_ms": 10000,
            },
        }
    )


def test_llm_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    assert score_with_llm(make_input()) is None


def test_missing_api_key_returns_none(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    assert score_with_llm(make_input()) is None


def test_json_parse_failure_returns_none(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    assert score_with_llm(make_input()) is None


def test_valid_json_can_parse():
    payload = parse_llm_json_result(
        """
        {
          "personality_openness": 101,
          "personality_conscientiousness": 65,
          "personality_extraversion": -4,
          "personality_agreeableness": 72,
          "personality_neuroticism": 22,
          "decision_style": "rational",
          "evidence": [{"trait": "personality_conscientiousness", "quote": "确认风险", "reason": "关注风险"}],
          "confidence": 0.92
        }
        """
    )

    assert payload["estimated_persona"]["personality_openness"] == 100
    assert payload["estimated_persona"]["personality_extraversion"] == 0
    assert payload["decision_style"] == "rational"
    assert payload["evidence"][0] == {
        "trait": "personality_conscientiousness",
        "quote": "确认风险",
        "reason": "关注风险",
    }


def test_llm_confidence_is_capped_at_point_75():
    payload = parse_llm_json_result(
        """
        {
          "personality_openness": 50,
          "personality_conscientiousness": 50,
          "personality_extraversion": 50,
          "personality_agreeableness": 50,
          "personality_neuroticism": 50,
          "decision_style": "balanced",
          "evidence": [],
          "confidence": 1
        }
        """
    )

    assert payload["confidence"] == 0.75
