from src.adapters.v04_event_adapter import build_score_input_from_v04_event


def make_event(**overrides):
    event = {
        "event_id": "EV_P_001_T3_A1",
        "session_id": "S_P_001",
        "user_id": "P_001",
        "participant_id": "P_001",
        "scene_id": "SCENE_T3",
        "scene_name": "有人反驳我？",
        "task_id": "3",
        "task_name": "有人反驳我？",
        "target_traits": "外向性 E,宜人性 A",
        "event_type": "main_answer",
        "prompt": "你会怎么回应？",
        "user_text": "我会先听完对方观点，再说明我的依据。",
        "quality_flags": [],
        "is_valid_event": True,
        "created_at": "2026-06-07T19:25:20+08:00",
    }
    event.update(overrides)
    return event


def test_v04_event_can_build_score_input():
    score_input = build_score_input_from_v04_event(make_event())

    assert score_input.dialogue_event.event_id == "EV_P_001_T3_A1"
    assert score_input.response_meta.event_id == "EV_P_001_T3_A1"


def test_metadata_keeps_session_user_and_scene_fields():
    score_input = build_score_input_from_v04_event(make_event())

    assert score_input.metadata.session_id == "S_P_001"
    assert score_input.metadata.user_id == "P_001"
    assert score_input.metadata.scene_name == "有人反驳我？"
    assert score_input.metadata.extra["scene_id"] == "SCENE_T3"
    assert score_input.metadata.extra["task_id"] == "3"
    assert score_input.metadata.extra["event_type"] == "main_answer"


def test_main_and_followup_round_ids_are_derived_from_task_id():
    main = build_score_input_from_v04_event(make_event(task_id="3", event_type="main_answer"))
    followup = build_score_input_from_v04_event(
        make_event(event_id="EV_P_001_T3_A2", task_id="3", event_type="followup_answer")
    )

    assert main.dialogue_event.round_id == 5
    assert followup.dialogue_event.round_id == 6


def test_prompt_and_user_text_mapping():
    score_input = build_score_input_from_v04_event(
        make_event(prompt="请说明原因。", user_text="我会补充风险和时间安排。")
    )

    assert score_input.dialogue_event.npc_dialogue_script == "请说明原因。"
    assert score_input.response_meta.user_free_text_input == "我会补充风险和时间安排。"


def test_empty_user_text_does_not_crash_adapter():
    score_input = build_score_input_from_v04_event(make_event(user_text=None, is_valid_event=False))

    assert score_input.response_meta.user_free_text_input is None
