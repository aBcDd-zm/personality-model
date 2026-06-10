from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any


TRAIT_FIELDS = [
    "personality_openness",
    "personality_conscientiousness",
    "personality_extraversion",
    "personality_agreeableness",
    "personality_neuroticism",
]

TRAIT_ALIASES = {
    "personality_openness": ("personality_openness", "openness", "O", "o"),
    "personality_conscientiousness": (
        "personality_conscientiousness",
        "conscientiousness",
        "C",
        "c",
    ),
    "personality_extraversion": ("personality_extraversion", "extraversion", "E", "e"),
    "personality_agreeableness": ("personality_agreeableness", "agreeableness", "A", "a"),
    "personality_neuroticism": ("personality_neuroticism", "neuroticism", "N", "n"),
}

TRAIT_TARGET_CODES = {
    "personality_openness": "O",
    "personality_conscientiousness": "C",
    "personality_extraversion": "E",
    "personality_agreeableness": "A",
    "personality_neuroticism": "N",
}

TARGET_TRAIT_NAMES = {
    "O": ("开放性", "openness"),
    "C": ("尽责性", "conscientiousness"),
    "E": ("外向性", "extraversion"),
    "A": ("宜人性", "agreeableness"),
    "N": ("神经质", "neuroticism"),
}

NON_TARGET_WEIGHT = 0.15
CONFIDENCE_THRESHOLD = 0.2
MAX_EVIDENCE = 10


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _target_trait_codes(event: dict[str, Any]) -> set[str]:
    raw = str(event.get("target_traits") or "")
    codes: set[str] = set()

    for code, names in TARGET_TRAIT_NAMES.items():
        if re.search(rf"(^|[^A-Za-z]){code}([^A-Za-z]|$)", raw):
            codes.add(code)
            continue
        if any(name in raw for name in names):
            codes.add(code)

    return codes


def _trait_event_weight(event: dict[str, Any], field: str) -> float:
    target_codes = _target_trait_codes(event)
    if not target_codes:
        return 1.0

    trait_code = TRAIT_TARGET_CODES[field]
    if trait_code in target_codes:
        return 1.0

    return NON_TARGET_WEIGHT


def _quality_flags(event: dict[str, Any]) -> list[str]:
    flags = event.get("quality_flags") or []
    if isinstance(flags, str):
        return [flag.strip() for flag in flags.split("|") if flag.strip()]
    if isinstance(flags, list):
        return [str(flag).strip() for flag in flags if str(flag).strip()]
    return []


def _is_low_quality(event: dict[str, Any]) -> bool:
    flags = {flag.lower() for flag in _quality_flags(event)}
    raw = str(event.get("quality_flag_raw") or "").lower()
    return event.get("is_low_quality") is True or "low_quality" in flags or raw == "low_quality"


def _score_source(event: dict[str, Any]) -> dict[str, Any]:
    final_result = event.get("final_result") or {}
    if not isinstance(final_result, dict):
        return {}
    estimated = final_result.get("estimated_persona")
    if isinstance(estimated, dict):
        return estimated
    scores = final_result.get("scores")
    if isinstance(scores, dict):
        return scores
    return final_result


def extract_trait_scores(event: dict[str, Any]) -> dict[str, float | None]:
    source = _score_source(event)
    scores: dict[str, float | None] = {}
    for trait, aliases in TRAIT_ALIASES.items():
        value = None
        for alias in aliases:
            if alias in source:
                value = _as_float(source.get(alias))
                break
        scores[trait] = value
    return scores


def is_aggregatable_event(event: dict[str, Any], *, confidence_threshold: float = CONFIDENCE_THRESHOLD) -> bool:
    confidence = _as_float(event.get("confidence"))
    return (
        event.get("scored") is True
        and event.get("is_valid_event") is True
        and event.get("is_demo") is not True
        and not _is_low_quality(event)
        and confidence is not None
        and confidence >= confidence_threshold
    )


def _dedupe_evidence(events: list[dict[str, Any]]) -> list[Any]:
    evidence: list[Any] = []
    seen: set[str] = set()
    for event in events:
        items = event.get("evidence") or []
        if not isinstance(items, list):
            items = [items]
        for item in items:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(item)
            if len(evidence) >= MAX_EVIDENCE:
                return evidence
    return evidence


def _weighted_scores(events: list[dict[str, Any]]) -> dict[str, float | None]:
    totals = {field: 0.0 for field in TRAIT_FIELDS}
    weights = {field: 0.0 for field in TRAIT_FIELDS}

    for event in events:
        confidence = _as_float(event.get("confidence"))
        if confidence is None:
            continue

        scores = extract_trait_scores(event)

        for field in TRAIT_FIELDS:
            score = scores.get(field)
            if score is None:
                continue

            trait_weight = _trait_event_weight(event, field)
            weight = confidence * trait_weight

            totals[field] += score * weight
            weights[field] += weight

    return {
        field: round(totals[field] / weights[field], 4) if weights[field] else None
        for field in TRAIT_FIELDS
    }


def _mean_confidence(events: list[dict[str, Any]]) -> float | None:
    confidences = [_as_float(event.get("confidence")) for event in events]
    values = [confidence for confidence in confidences if confidence is not None]
    return round(sum(values) / len(values), 4) if values else None


def _group_events(scored_events: list[dict[str, Any]], key_fields: tuple[str, ...]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in scored_events:
        groups[tuple(event.get(field) for field in key_fields)].append(event)
    return groups


def aggregate_scene_scores(scored_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = _group_events(scored_events, ("session_id", "user_id", "scene_id", "task_id"))
    rows: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda item: tuple("" if value is None else str(value) for value in item)):
        events = groups[key]
        first = events[0]
        aggregate_events = [event for event in events if is_aggregatable_event(event)]
        has_scores = bool(aggregate_events)
        rows.append(
            {
                "session_id": first.get("session_id"),
                "user_id": first.get("user_id"),
                "scene_id": first.get("scene_id"),
                "scene_name": first.get("scene_name"),
                "task_id": first.get("task_id"),
                "event_count": len(events),
                "aggregated_event_count": len(aggregate_events),
                "skipped_event_count": len(events) - len(aggregate_events),
                "scene_score": _weighted_scores(aggregate_events) if has_scores else {field: None for field in TRAIT_FIELDS},
                "scene_confidence": _mean_confidence(aggregate_events),
                "evidence": _dedupe_evidence(aggregate_events),
                "aggregation_status": "ok" if has_scores else "no_valid_events",
            }
        )
    return rows


def aggregate_session_scores(scored_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = _group_events(scored_events, ("session_id", "user_id"))
    rows: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda item: tuple("" if value is None else str(value) for value in item)):
        events = groups[key]
        first = events[0]
        aggregate_events = [event for event in events if is_aggregatable_event(event)]
        has_scores = bool(aggregate_events)
        rows.append(
            {
                "session_id": first.get("session_id"),
                "user_id": first.get("user_id"),
                "event_count": len(events),
                "aggregated_event_count": len(aggregate_events),
                "skipped_event_count": len(events) - len(aggregate_events),
                "scene_count": len({event.get("scene_id") for event in events}),
                "session_score": _weighted_scores(aggregate_events) if has_scores else {field: None for field in TRAIT_FIELDS},
                "session_confidence": _mean_confidence(aggregate_events),
                "evidence": _dedupe_evidence(aggregate_events),
                "aggregation_status": "ok" if has_scores else "no_valid_events",
            }
        )
    return rows
