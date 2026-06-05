from src.rule_scorer import score_with_rules
from src.schemas import ScoreInput


def make_input(text=None, option=None, response_type="FreeText"):
    return ScoreInput.from_dict(
        {
            "metadata": {"session_id": "S001"},
            "dialogue_event": {
                "event_id": "EV_001",
                "game_id": "G001",
                "round_id": 1,
                "npc_role": "熊老板",
                "trigger_condition": {"time_pressure_level": 8},
                "npc_dialogue_script": "你打算怎么处理？",
                "user_response_type": response_type,
            },
            "response_meta": {
                "event_id": "EV_001",
                "user_free_text_input": text,
                "user_selected_option": option,
                "response_time_ms": 12000,
            },
        }
    )


def test_responsible_answer_raises_conscientiousness():
    result = score_with_rules(make_input("我会制定计划，确认关键风险，保证质量和交付，并在结束后复盘。"))

    assert result.estimated_persona.personality_conscientiousness >= 60


def test_cooperative_answer_raises_agreeableness():
    result = score_with_rules(make_input("我会先安抚同事，理解他的压力，再协调团队一起合作支持。"))

    assert result.estimated_persona.personality_agreeableness >= 65


def test_anxious_attack_answer_raises_neuroticism():
    result = score_with_rules(make_input("我现在很焦虑，压力太大了，这事完蛋了，先攻击甩锅给别人吧。"))

    assert result.estimated_persona.personality_neuroticism >= 70


def test_innovative_answer_raises_openness():
    result = score_with_rules(make_input("我想提出一个创新的新方案，尝试新路径，先做小实验再突破。"))

    assert result.estimated_persona.personality_openness >= 70


def test_feedback_actor_id_defaults_to_player():
    result = score_with_rules(make_input("我会确认方案。"))

    assert result.feedback.actor_id == "玩家"


def test_option_maps_to_strategy_profile():
    result = score_with_rules(make_input(text=None, option=4, response_type="Option"))

    assert result.estimated_persona.personality_openness >= 80
    assert result.feedback.actor_id == "玩家"

