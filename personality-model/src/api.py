from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from src.adapters.common import build_score_input_from_payload
from src.aggregation import aggregate_session_scores
from src.hybrid_scorer import score
from src.llm_scorer import llm_fallback_reason
from src.report_builder import build_session_report
from src.schemas import ScoreResult, SchemaValidationError


API_VERSION = "personality_model_api_v1"
CONFIDENCE_THRESHOLD = 0.2
DATA_DIR = Path("data/sessions")
DEFAULT_USE_LLM = os.getenv("PERSONALITY_USE_LLM", "").lower() in {
    "1",
    "true",
    "yes",
    "y",
}


app = FastAPI(
    title="Personality Model Scoring API",
    version=API_VERSION,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: Any) -> str:
    text = str(value or "unknown_session").strip()
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text) or "unknown_session"


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return str(value)


def _normalize_response_meta(response_meta: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(response_meta or {})

    # 兼容主项目可能传来的短字段名
    alias_map = {
        "sentiment": "response_sentiment",
        "lexical_diversity": "response_lexical_diversity",
        "self_focus_ratio": "response_self_focus_ratio",
    }
    for old_key, new_key in alias_map.items():
        if old_key in data and new_key not in data:
            data[new_key] = data[old_key]

    # 如果后端暂时没给 response_length，这里先补一个基础长度
    if data.get("response_length") is None:
        text = str(data.get("user_free_text_input") or "")
        if text:
            data["response_length"] = len("".join(text.split()))

    return data


def _normalize_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metadata = dict(payload.get("metadata") or {})
    dialogue_event = dict(payload.get("dialogue_event") or {})
    response_meta = _normalize_response_meta(payload.get("response_meta") or {})

    # 主项目文档里 game_id / round_id 有时在 metadata，这里补到 dialogue_event
    if not dialogue_event.get("game_id"):
        dialogue_event["game_id"] = metadata.get("game_id") or metadata.get("session_id") or "unknown_game"

    if dialogue_event.get("round_id") is None:
        dialogue_event["round_id"] = metadata.get("round_id") or 0

    # response_meta.event_id 如果没传，就从 dialogue_event 补
    if not response_meta.get("event_id") and dialogue_event.get("event_id"):
        response_meta["event_id"] = dialogue_event["event_id"]

    return metadata, dialogue_event, response_meta


def _score_payload(payload: dict[str, Any]) -> ScoreResult:
    metadata, dialogue_event, response_meta = _normalize_payload(payload)

    score_input = build_score_input_from_payload(
        metadata=metadata,
        dialogue_event=dialogue_event,
        response_meta=response_meta,
    )

    method = str(payload.get("method") or payload.get("scoring_method") or "").strip().lower()
    if not method:
        if score_input.dialogue_event.user_response_type == "Option":
            method = "rule"
        else:
            method = "hybrid"

    use_llm = _truthy(payload.get("use_llm"), DEFAULT_USE_LLM)

    return score(score_input, method=method, use_llm=use_llm)


def _short_persona(scores: dict[str, Any]) -> dict[str, float | None]:
    return {
        "openness": _round_or_none(scores.get("personality_openness")),
        "conscientiousness": _round_or_none(scores.get("personality_conscientiousness")),
        "extraversion": _round_or_none(scores.get("personality_extraversion")),
        "agreeableness": _round_or_none(scores.get("personality_agreeableness")),
        "neuroticism": _round_or_none(scores.get("personality_neuroticism")),
    }


def _quality_is_low(metadata: dict[str, Any]) -> bool:
    flags = metadata.get("quality_flags") or []
    if isinstance(flags, str):
        flags = [item.strip() for item in flags.split("|") if item.strip()]
    return any("low_quality" in str(flag).lower() for flag in flags)


def _is_result_aggregatable(result: ScoreResult) -> bool:
    metadata = result.metadata.to_dict()

    if result.confidence < CONFIDENCE_THRESHOLD:
        return False
    if _truthy(metadata.get("is_demo"), False):
        return False
    if not _truthy(metadata.get("is_valid_event"), True):
        return False
    if _quality_is_low(metadata):
        return False

    return True


def _dominant_decision_style(results: list[ScoreResult]) -> str:
    weights: dict[str, float] = defaultdict(float)

    for result in results:
        style = str(result.decision_style or "unclear")
        weights[style] += float(result.confidence or 0)

    if not weights:
        return "unclear"

    return max(weights.items(), key=lambda item: item[1])[0]


def _session_report_payload(report: Any, results: list[ScoreResult]) -> dict[str, Any]:
    data = report.to_dict()
    average_persona = data.get("average_estimated_persona") or {}

    data["estimated_persona"] = _short_persona(average_persona)
    data["decision_style"] = _dominant_decision_style(results)
    data["confidence"] = data.get("average_confidence")
    data["scoring_method"] = "hybrid_session"

    return data


def _event_record(result: ScoreResult, payload: dict[str, Any]) -> dict[str, Any]:
    result_dict = result.to_dict()
    metadata = result.metadata.to_dict()
    dialogue_event = result.dialogue_event.to_dict()

    final_result = result_dict.get("final_result") or {
        "estimated_persona": result_dict.get("estimated_persona"),
        "feedback": result_dict.get("feedback"),
        "decision_style": result_dict.get("decision_style"),
        "evidence": result_dict.get("evidence"),
        "confidence": result_dict.get("confidence"),
        "scoring_method": result_dict.get("scoring_method"),
        "prompt_version": result_dict.get("prompt_version"),
        "model_version": result_dict.get("model_version"),
    }

    return {
        "recorded_at": _now_iso(),
        "session_id": metadata.get("session_id"),
        "user_id": metadata.get("user_id"),
        "game_id": dialogue_event.get("game_id"),
        "round_id": dialogue_event.get("round_id"),
        "event_id": dialogue_event.get("event_id"),
        "scene_name": metadata.get("scene_name"),
        "scene_id": metadata.get("scene_id"),
        "task_id": metadata.get("task_id"),
        "target_traits": metadata.get("target_traits"),
        "user_response_type": dialogue_event.get("user_response_type"),
        "is_demo": _truthy(metadata.get("is_demo") or payload.get("is_demo"), False),
        "is_valid_event": _truthy(metadata.get("is_valid_event"), True),
        "quality_flags": metadata.get("quality_flags") or [],
        "scored": True,
        "confidence": result.confidence,
        "evidence": result_dict.get("evidence") or [],
        "final_result": final_result,
        "result": result_dict,
    }


def _append_event_record(record: dict[str, Any]) -> Path:
    session_id = record.get("session_id") or record.get("game_id") or "unknown_session"
    session_dir = DATA_DIR / _safe_id(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    output_path = session_dir / "scored_events.jsonl"
    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")

    return output_path


def _load_session_records(session_id: str) -> list[dict[str, Any]]:
    output_path = DATA_DIR / _safe_id(session_id) / "scored_events.jsonl"
    if not output_path.exists():
        return []

    records = []
    with output_path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))

    return records


def _dominant_decision_style_from_records(records: list[dict[str, Any]]) -> str:
    weights: dict[str, float] = defaultdict(float)

    for record in records:
        final_result = record.get("final_result") or {}
        style = str(final_result.get("decision_style") or "unclear")
        confidence = _round_or_none(final_result.get("confidence"))
        if confidence is None:
            confidence = _round_or_none(record.get("confidence")) or 0.0
        weights[style] += confidence

    if not weights:
        return "unclear"

    return max(weights.items(), key=lambda item: item[1])[0]


def _session_report_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = aggregate_session_scores(records)
    if not rows:
        return {
            "session_id": None,
            "event_count": 0,
            "estimated_persona": {},
            "average_estimated_persona": {},
            "evidence": [],
            "confidence": 0.0,
            "average_confidence": 0.0,
            "decision_style": "unclear",
            "scoring_method": "hybrid_session",
        }

    row = rows[0]
    session_score = row.get("session_score") or {}

    return {
        "session_id": row.get("session_id"),
        "user_id": row.get("user_id"),
        "event_count": row.get("event_count"),
        "aggregated_event_count": row.get("aggregated_event_count"),
        "skipped_event_count": row.get("skipped_event_count"),
        "average_estimated_persona": session_score,
        "estimated_persona": _short_persona(session_score),
        "evidence": row.get("evidence") or [],
        "average_confidence": row.get("session_confidence") or 0.0,
        "confidence": row.get("session_confidence") or 0.0,
        "decision_style": _dominant_decision_style_from_records(records),
        "scoring_method": "hybrid_session",
        "aggregation_status": row.get("aggregation_status"),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    fallback = llm_fallback_reason()
    llm_available = fallback is None

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "llm_available": llm_available,
        "llm_default_enabled": DEFAULT_USE_LLM,
        "llm_fallback_reason": fallback,
    }


@app.post("/score/event")
def score_event(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = _score_payload(payload)
        record = _event_record(result, payload)
        _append_event_record(record)

        response = result.to_dict()
        response["api_version"] = API_VERSION
        return response

    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/score/session")
def score_session(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        events = payload.get("events")

        # 情况 A：后端直接传一组原始事件，API 现场评分并汇总
        if events is not None:
            if not isinstance(events, list):
                raise HTTPException(status_code=400, detail="events must be a list")

            results = [_score_payload(event) for event in events]
            aggregatable_results = [
                result for result in results if _is_result_aggregatable(result)
            ]

            report = build_session_report(aggregatable_results)
            session_report = _session_report_payload(report, aggregatable_results)

            if _truthy(payload.get("persist_events"), False):
                for event_payload, result in zip(events, results):
                    _append_event_record(_event_record(result, event_payload))

            return {
                "api_version": API_VERSION,
                "events": [result.to_dict() for result in results],
                "session_report": session_report,
            }

        # 情况 B：后端只传 session_id，API 从本地 scored_events.jsonl 读取已评分事件并汇总
        session_id = payload.get("session_id")
        if not session_id and isinstance(payload.get("metadata"), dict):
            session_id = payload["metadata"].get("session_id")

        if session_id:
            records = _load_session_records(str(session_id))
            if not records:
                raise HTTPException(
                    status_code=404,
                    detail=f"No scored events found for session_id={session_id}",
                )

            return {
                "api_version": API_VERSION,
                "events": records,
                "session_report": _session_report_from_records(records),
            }

        raise HTTPException(
            status_code=400,
            detail="Request must include either events or session_id",
        )

    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
