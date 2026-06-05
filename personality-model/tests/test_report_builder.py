from src.report_builder import build_session_report
from src.rule_scorer import score_with_rules
from src.schemas import ScoreInput


def make_input(event_id, round_id, text):
    return ScoreInput.from_dict(
        {
            "metadata": {"session_id": "S001"},
            "dialogue_event": {
                "event_id": event_id,
                "game_id": "G001",
                "round_id": round_id,
                "npc_role": "熊市场",
                "trigger_condition": {},
                "npc_dialogue_script": "你怎么看？",
                "user_response_type": "FreeText",
            },
            "response_meta": {
                "event_id": event_id,
                "user_free_text_input": text,
                "response_time_ms": 10000,
            },
        }
    )


def test_session_report_summarizes_multiple_rounds():
    results = [
        score_with_rules(make_input("EV_001", 1, "我会确认风险，保证质量和交付。")),
        score_with_rules(make_input("EV_002", 2, "我会协调团队合作，提出一个新方案。")),
    ]

    report = build_session_report(results)

    assert report.event_count == 2
    assert "personality_openness" in report.average_estimated_persona
    assert "openness_change" in report.total_feedback


def test_evidence_is_preserved():
    results = [score_with_rules(make_input("EV_001", 1, "我会协调团队合作。"))]

    report = build_session_report(results)

    assert report.evidence
    assert any("宜人性" in item or "合作" in item for item in report.evidence)

