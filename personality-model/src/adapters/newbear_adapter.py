from __future__ import annotations

from datetime import datetime
from typing import Any

from src.adapters.common import build_score_input_from_payload
from src.schemas import ScoreInput


def _value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _get_game_id(user: Any, world: Any) -> str:
    return str(_value(world, "session_record_id") or _value(user, "session_id"))


def _clean_clock(clock: Any) -> str:
    return str(clock or "").replace(":", "")


def _last_non_user_line(transcript: Any) -> Any | None:
    for line in reversed(list(transcript or [])):
        actor_id = str(_value(line, "actor_id", "") or "")
        kind = str(_value(line, "kind", "") or "")
        role = str(_value(line, "role", "") or "")
        if actor_id != "user" and kind != "user" and role != "user":
            return line
    return None


def _line_text(line: Any | None) -> str:
    if not line:
        return ""
    return str(_value(line, "content") or _value(line, "speech") or _value(line, "text") or "")


def _line_speaker(line: Any | None) -> str:
    if not line:
        return ""
    return str(
        _value(line, "speaker")
        or _value(line, "display_name")
        or _value(line, "actor_id")
        or ""
    )


def _company(world: Any) -> Any:
    return _value(world, "company", {})


def _build_meeting_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    meeting = _value(world, "active_meeting")
    company = _company(world)
    if meeting is None:
        return (
            "会议 NPC",
            "玩家在会议场景中发言。",
            {"scene": "meeting", "day": _value(company, "day"), "step": _value(company, "step"), "clock": _value(company, "clock")},
            "meeting",
        )

    last_npc_line = _last_non_user_line(_value(meeting, "transcript"))
    npc_role = _line_speaker(last_npc_line) or "会议 NPC"
    npc_script = (
        _line_text(last_npc_line)
        or _value(meeting, "content")
        or _value(meeting, "title")
        or "玩家在会议场景中发言。"
    )
    meeting_id = _value(meeting, "meeting_id", "meeting")
    return (
        npc_role,
        str(npc_script),
        {
            "scene": "meeting",
            "meeting_id": meeting_id,
            "title": _value(meeting, "title"),
            "content": _value(meeting, "content"),
            "phase": _value(meeting, "phase"),
            "participants": _value(meeting, "participants"),
            "day": _value(company, "day"),
            "step": _value(company, "step"),
            "clock": _value(company, "clock"),
        },
        str(meeting_id),
    )


def _build_pantry_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    pantry = _value(world, "active_pantry")
    company = _company(world)
    if pantry is None:
        return (
            "茶水间 NPC",
            "玩家在茶水间场景中发言。",
            {"scene": "pantry", "day": _value(company, "day"), "step": _value(company, "step"), "clock": _value(company, "clock")},
            "pantry",
        )

    last_npc_line = _last_non_user_line(_value(pantry, "transcript"))
    npc_role = _line_speaker(last_npc_line) or "茶水间 NPC"
    npc_script = (
        _line_text(last_npc_line)
        or _value(pantry, "content")
        or _value(pantry, "title")
        or "玩家在茶水间场景中发言。"
    )
    pantry_id = _value(pantry, "pantry_id", "pantry")
    return (
        npc_role,
        str(npc_script),
        {
            "scene": "pantry",
            "pantry_id": pantry_id,
            "title": _value(pantry, "title"),
            "content": _value(pantry, "content"),
            "phase": _value(pantry, "phase"),
            "participants": _value(pantry, "participants"),
            "day": _value(company, "day"),
            "step": _value(company, "step"),
            "clock": _value(company, "clock"),
        },
        str(pantry_id),
    )


def _build_world_context(world: Any) -> tuple[str, str, dict[str, Any], str]:
    company = _company(world)
    pending_incident = _value(world, "pending_incident")
    if pending_incident is not None:
        npc_script = f"{_value(pending_incident, 'title')}：{_value(pending_incident, 'content')}"
        subject_id = _value(pending_incident, "incident_id", "world")
    else:
        npc_script = "玩家在世界主流程中输入事务处理方案。"
        subject_id = "world"
    return (
        "系统",
        npc_script,
        {
            "scene": "world",
            "company_name": _value(company, "name"),
            "company_phase": _value(company, "phase"),
            "cash": _value(company, "cash"),
            "day": _value(company, "day"),
            "step": _value(company, "step"),
            "clock": _value(company, "clock"),
            "pending_incident_id": _value(pending_incident, "incident_id"),
            "pending_incident_title": _value(pending_incident, "title"),
        },
        str(subject_id),
    )


def _build_scene_context(world: Any, scene: str) -> tuple[str, str, dict[str, Any], str]:
    if scene == "meeting":
        return _build_meeting_context(world)
    if scene == "pantry":
        return _build_pantry_context(world)
    return _build_world_context(world)


def _build_event_id(*, game_id: str, scene: str, world: Any, subject_id: str, counter: int) -> str:
    company = _company(world)
    return (
        f"{game_id}:{scene}:day{_value(company, 'day')}:"
        f"step{_value(company, 'step')}:clock{_clean_clock(_value(company, 'clock'))}:"
        f"{subject_id}:{counter}"
    )


def _counter_for_scene(world: Any, scene: str) -> int:
    if scene == "meeting" and _value(world, "active_meeting") is not None:
        return len(_value(_value(world, "active_meeting"), "transcript", []) or []) + 1
    if scene == "pantry" and _value(world, "active_pantry") is not None:
        return len(_value(_value(world, "active_pantry"), "transcript", []) or []) + 1
    return len(_value(world, "user_inputs", []) or []) + 1


def build_score_input_from_world(
    *,
    user: Any,
    world: Any,
    scene: str,
    user_text: str,
    selected_option: int | None = None,
    response_time_ms: int | None = None,
) -> ScoreInput:
    """Convert newbear runtime state into ScoreInput without importing newbear types."""

    clean_scene = str(scene or "world").strip() or "world"
    clean_user_text = str(user_text or "").strip()
    game_id = _get_game_id(user, world)
    company = _company(world)
    npc_role, npc_script, trigger_condition, subject_id = _build_scene_context(world, clean_scene)
    counter = _counter_for_scene(world, clean_scene)
    event_id = _build_event_id(
        game_id=game_id,
        scene=clean_scene,
        world=world,
        subject_id=subject_id,
        counter=counter,
    )
    metadata = {
        "session_id": game_id,
        "user_id": str(_value(user, "user_id")),
        "scene_name": clean_scene,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "clock": _value(company, "clock"),
        "day": _value(company, "day"),
        "step": _value(company, "step"),
        "auth_session_id": str(_value(user, "session_id")),
        "world_session_record_id": str(_value(world, "session_record_id") or ""),
    }
    dialogue_event = {
        "event_id": event_id,
        "game_id": game_id,
        "round_id": int(_value(company, "step")),
        "npc_role": npc_role,
        "trigger_condition": trigger_condition,
        "npc_dialogue_script": npc_script,
        "user_response_type": "Option" if selected_option is not None else "FreeText",
    }
    response_meta = {
        "event_id": event_id,
        "user_free_text_input": clean_user_text,
        "user_selected_option": selected_option,
        "response_time_ms": response_time_ms,
    }
    return build_score_input_from_payload(
        metadata=metadata,
        dialogue_event=dialogue_event,
        response_meta=response_meta,
    )
