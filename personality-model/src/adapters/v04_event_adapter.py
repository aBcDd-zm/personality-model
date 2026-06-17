from __future__ import annotations

from typing import Any

from src.adapters.common import build_score_input_from_payload
from src.schemas import ScoreInput


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _round_id(task_id: Any, event_type: Any) -> int:
    task_number = int(str(task_id).strip())
    if event_type == "main_answer":
        return task_number * 2 - 1
    return task_number * 2


def build_score_input_from_v04_event(event: dict[str, Any]) -> ScoreInput:
    """Convert one v0.4 event row into the personality-model ScoreInput."""

    event_id = _text(event.get("event_id")).strip()
    session_id = _text(event.get("session_id")).strip()
    task_id = event.get("task_id")
    event_type = event.get("event_type")

    metadata = {
        "session_id": session_id,
        "user_id": event.get("user_id"),
        "scene_name": event.get("scene_name"),
        "timestamp": event.get("created_at"),
        "participant_id": event.get("participant_id"),
        "scene_id": event.get("scene_id"),
        "task_id": event.get("task_id"),
        "task_name": event.get("task_name"),
        "target_traits": event.get("target_traits"),
        "event_type": event.get("event_type"),
        "is_valid_event": event.get("is_valid_event"),
        "quality_flags": event.get("quality_flags") or [],
    }
    dialogue_event = {
        "event_id": event_id,
        "game_id": session_id,
        "round_id": _round_id(task_id, event_type),
        "npc_role": "情境任务",
        "trigger_condition": {
            "scene_id": event.get("scene_id"),
            "task_id": event.get("task_id"),
            "target_traits": event.get("target_traits"),
            "event_type": event.get("event_type"),
        },
        "npc_dialogue_script": event.get("prompt") or "",
        "user_response_type": "FreeText",
    }
    response_meta = {
        "event_id": event_id,
        "user_free_text_input": event.get("user_text"),
        "user_selected_option": None,
        "response_time_ms": None,
    }
    return build_score_input_from_payload(
        metadata=metadata,
        dialogue_event=dialogue_event,
        response_meta=response_meta,
    )
