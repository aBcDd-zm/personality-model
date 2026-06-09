from __future__ import annotations

from typing import Any

from src.schemas import ScoreInput


def build_score_input_from_payload(
    *,
    metadata: dict[str, Any],
    dialogue_event: dict[str, Any],
    response_meta: dict[str, Any],
) -> ScoreInput:
    """Build a ScoreInput from the shared adapter payload structure."""

    return ScoreInput.from_dict(
        {
            "metadata": metadata,
            "dialogue_event": dialogue_event,
            "response_meta": response_meta,
        }
    )
