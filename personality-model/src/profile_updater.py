from __future__ import annotations

from typing import Any

from src.aggregation import TRAIT_FIELDS


def initial_profile() -> dict[str, float]:
    return {field: 50.0 for field in TRAIT_FIELDS}


def _score_payload(session_score: dict[str, Any]) -> dict[str, Any]:
    score = session_score.get("session_score")
    if isinstance(score, dict):
        return score
    return session_score


def update_profile(
    old_profile: dict[str, Any] | None,
    session_score: dict[str, Any],
    alpha: float = 0.2,
) -> dict[str, float]:
    base = initial_profile()
    if old_profile:
        for field in TRAIT_FIELDS:
            if old_profile.get(field) is not None:
                base[field] = float(old_profile[field])

    score = _score_payload(session_score)
    updated: dict[str, float] = {}
    for field in TRAIT_FIELDS:
        value = score.get(field)
        if value is None:
            updated[field] = round(base[field], 2)
            continue
        updated[field] = round((1 - alpha) * base[field] + alpha * float(value), 2)
    return updated
