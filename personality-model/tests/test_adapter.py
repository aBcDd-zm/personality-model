from types import SimpleNamespace

from src.adapter import build_score_input_from_world


def make_world(**overrides):
    world = {
        "session_record_id": "game-001",
        "company": {
            "name": "想想科技",
            "phase": "seed",
            "cash": 100000,
            "day": 2,
            "step": 3,
            "clock": "09:30",
        },
        "pending_incident": None,
        "active_meeting": None,
        "active_pantry": None,
        "user_inputs": ["old answer"],
    }
    world.update(overrides)
    return world


def test_builds_world_score_input_from_pending_incident():
    user = {"user_id": "u-1", "session_id": "auth-1"}
    world = make_world(
        pending_incident={
            "incident_id": "inc-7",
            "title": "线上事故",
            "content": "客户反馈登录失败。",
        }
    )

    score_input = build_score_input_from_world(
        user=user,
        world=world,
        scene="world",
        user_text="我会先确认影响范围，再安排修复。",
    )

    assert score_input.metadata.session_id == "game-001"
    assert score_input.metadata.extra["clock"] == "09:30"
    assert score_input.dialogue_event.event_id == score_input.response_meta.event_id
    assert score_input.dialogue_event.event_id == "game-001:world:day2:step3:clock0930:inc-7:2"
    assert score_input.dialogue_event.npc_role == "系统"
    assert score_input.dialogue_event.npc_dialogue_script == "线上事故：客户反馈登录失败。"
    assert score_input.response_meta.user_free_text_input == "我会先确认影响范围，再安排修复。"


def test_builds_meeting_score_input_from_last_npc_line():
    user = SimpleNamespace(user_id="u-2", session_id="auth-2")
    meeting = SimpleNamespace(
        meeting_id="m-1",
        title="晨会",
        content="大家同步进度。",
        phase="open",
        participants=["user", "xionglaoban"],
        transcript=[
            {"actor_id": "xionglaoban", "speaker": "熊老板", "content": "今天必须上线。"},
            {"actor_id": "user", "kind": "user", "content": "我先看风险。"},
        ],
    )
    world = make_world(active_meeting=meeting)

    score_input = build_score_input_from_world(
        user=user,
        world=world,
        scene="meeting",
        user_text="我会拆出最小上线范围。",
        response_time_ms=12000,
    )

    assert score_input.dialogue_event.npc_role == "熊老板"
    assert score_input.dialogue_event.npc_dialogue_script == "今天必须上线。"
    assert score_input.dialogue_event.trigger_condition["meeting_id"] == "m-1"
    assert score_input.dialogue_event.event_id == "game-001:meeting:day2:step3:clock0930:m-1:3"
    assert score_input.response_meta.response_time_ms == 12000


def test_builds_pantry_option_score_input_from_dict_transcript():
    user = {"user_id": "u-3", "session_id": "auth-3"}
    world = make_world(
        session_record_id=None,
        active_pantry={
            "pantry_id": "p-1",
            "title": "茶水间闲聊",
            "content": "同事压力很大。",
            "phase": "chat",
            "participants": ["user", "xiongxingzheng"],
            "transcript": [
                {"actor_id": "user", "kind": "user", "content": "怎么了？"},
                {"actor_id": "xiongxingzheng", "display_name": "熊行政", "text": "最近任务太满了。"},
            ],
        },
    )

    score_input = build_score_input_from_world(
        user=user,
        world=world,
        scene="pantry",
        user_text="  选第二个方案  ",
        selected_option=2,
    )

    assert score_input.metadata.session_id == "auth-3"
    assert score_input.dialogue_event.game_id == "auth-3"
    assert score_input.dialogue_event.user_response_type == "Option"
    assert score_input.dialogue_event.npc_role == "熊行政"
    assert score_input.dialogue_event.npc_dialogue_script == "最近任务太满了。"
    assert score_input.response_meta.user_free_text_input == "选第二个方案"
    assert score_input.response_meta.user_selected_option == 2
