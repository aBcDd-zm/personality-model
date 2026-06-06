from src.hybrid_scorer import score
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


def llm_payload(**scores):
    base = {
        "personality_openness": 70,
        "personality_conscientiousness": 70,
        "personality_extraversion": 50,
        "personality_agreeableness": 70,
        "personality_neuroticism": 20,
    }
    base.update(scores)
    return {
        "estimated_persona": base,
        "decision_style": "rational",
        "evidence": [{"trait": "personality_conscientiousness", "quote": "确认风险", "reason": "关注风险"}],
        "confidence": 0.7,
        "prompt_version": "zero_shot_v1",
        "model_version": "deepseek-chat",
    }


def test_llm_disabled_final_result_equals_rule_result(monkeypatch):
    monkeypatch.setattr("src.hybrid_scorer.llm_fallback_reason", lambda: "LLM_DISABLED")

    result = score(make_input(), method="hybrid", use_llm=True)
    data = result.to_dict()

    assert data["final_result"] == data["rule_result"]
    assert data["scoring_trace"]["llm_used"] is False
    assert data["scoring_trace"]["fallback_reason"] == "LLM_DISABLED"


def test_llm_success_generates_hybrid_result(monkeypatch):
    monkeypatch.setattr("src.hybrid_scorer.llm_fallback_reason", lambda: None)
    monkeypatch.setattr("src.hybrid_scorer.score_with_llm", lambda score_input: llm_payload())

    result = score(make_input(), method="hybrid", use_llm=True)
    data = result.to_dict()

    assert data["llm_result"] is not None
    assert data["hybrid_result"] is not None
    assert data["final_result"] == data["hybrid_result"]
    assert data["scoring_trace"]["llm_used"] is True


def test_large_rule_llm_disagreement_lowers_hybrid_confidence(monkeypatch):
    monkeypatch.setattr("src.hybrid_scorer.llm_fallback_reason", lambda: None)
    monkeypatch.setattr(
        "src.hybrid_scorer.score_with_llm",
        lambda score_input: llm_payload(
            personality_openness=0,
            personality_conscientiousness=0,
            personality_extraversion=100,
            personality_agreeableness=0,
            personality_neuroticism=100,
        ),
    )

    result = score(make_input(), method="hybrid", use_llm=True)

    assert result.confidence < result.rule_result["confidence"]


def test_scoring_trace_records_missing_api_key(monkeypatch):
    monkeypatch.setattr("src.hybrid_scorer.llm_fallback_reason", lambda: "MISSING_API_KEY")

    result = score(make_input(), method="hybrid", use_llm=True)

    assert result.scoring_trace == {
        "llm_enabled": False,
        "llm_used": False,
        "fallback_reason": "MISSING_API_KEY",
    }
