from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RESPONSE_TYPES = {"FreeText", "Option", "Action"}
DEFAULT_ACTOR_ID = "玩家"


class SchemaValidationError(ValueError):
    """Raised when an input payload does not match the scoring contract."""


def _require_non_empty(value: Any, field_name: str) -> str:
    if value is None or str(value).strip() == "":
        raise SchemaValidationError(f"{field_name} is required")
    return str(value)


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise SchemaValidationError(f"{field_name} must be an integer")
    try:
        converted = int(value)
    except (TypeError, ValueError) as exc:
        raise SchemaValidationError(f"{field_name} must be an integer") from exc
    if converted != value and not isinstance(value, str):
        raise SchemaValidationError(f"{field_name} must be an integer")
    return converted


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


@dataclass(slots=True)
class Metadata:
    """Optional non-M1-M9 metadata used for demo export and validation matching."""

    session_id: str | None = None
    user_id: str | None = None
    scene_name: str | None = None
    timestamp: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "Metadata":
        if not payload:
            return cls()
        known = {key: payload.get(key) for key in ("session_id", "user_id", "scene_name", "timestamp")}
        extra = {key: value for key, value in payload.items() if key not in known}
        return cls(**known, extra=extra)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "scene_name": self.scene_name,
            "timestamp": self.timestamp,
        }
        data.update(self.extra)
        return {key: value for key, value in data.items() if value is not None}


@dataclass(slots=True)
class DialogueEvent:
    event_id: str
    game_id: str
    round_id: int
    npc_role: str
    trigger_condition: dict[str, Any] | None
    npc_dialogue_script: str
    user_response_type: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DialogueEvent":
        event_id = _require_non_empty(payload.get("event_id"), "dialogue_event.event_id")
        game_id = _require_non_empty(payload.get("game_id"), "dialogue_event.game_id")
        round_id = _require_int(payload.get("round_id"), "dialogue_event.round_id")
        npc_role = _require_non_empty(payload.get("npc_role"), "dialogue_event.npc_role")
        user_response_type = _require_non_empty(
            payload.get("user_response_type"), "dialogue_event.user_response_type"
        )
        if user_response_type not in RESPONSE_TYPES:
            raise SchemaValidationError(
                "dialogue_event.user_response_type must be one of FreeText, Option, Action"
            )
        return cls(
            event_id=event_id,
            game_id=game_id,
            round_id=round_id,
            npc_role=npc_role,
            trigger_condition=payload.get("trigger_condition"),
            npc_dialogue_script=str(payload.get("npc_dialogue_script") or ""),
            user_response_type=user_response_type,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "game_id": self.game_id,
            "round_id": self.round_id,
            "npc_role": self.npc_role,
            "trigger_condition": self.trigger_condition,
            "npc_dialogue_script": self.npc_dialogue_script,
            "user_response_type": self.user_response_type,
        }


@dataclass(slots=True)
class ResponseMeta:
    event_id: str
    user_free_text_input: str | None = None
    user_selected_option: int | None = None
    response_length: int | None = None
    response_sentiment: float | None = None
    response_lexical_diversity: float | None = None
    response_self_focus_ratio: float | None = None
    response_time_ms: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResponseMeta":
        event_id = _require_non_empty(payload.get("event_id"), "response_meta.event_id")
        selected = payload.get("user_selected_option")
        if selected is not None:
            selected = _require_int(selected, "response_meta.user_selected_option")
        response_time = payload.get("response_time_ms")
        if response_time is not None:
            response_time = _require_int(response_time, "response_meta.response_time_ms")
        response_length = payload.get("response_length")
        if response_length is not None:
            response_length = _require_int(response_length, "response_meta.response_length")
        return cls(
            event_id=event_id,
            user_free_text_input=payload.get("user_free_text_input"),
            user_selected_option=selected,
            response_length=response_length,
            response_sentiment=payload.get("response_sentiment"),
            response_lexical_diversity=payload.get("response_lexical_diversity"),
            response_self_focus_ratio=payload.get("response_self_focus_ratio"),
            response_time_ms=response_time,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_free_text_input": self.user_free_text_input,
            "user_selected_option": self.user_selected_option,
            "response_length": self.response_length,
            "response_sentiment": self.response_sentiment,
            "response_lexical_diversity": self.response_lexical_diversity,
            "response_self_focus_ratio": self.response_self_focus_ratio,
            "response_time_ms": self.response_time_ms,
        }


@dataclass(slots=True)
class ScoreInput:
    dialogue_event: DialogueEvent
    response_meta: ResponseMeta
    metadata: Metadata = field(default_factory=Metadata)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ScoreInput":
        dialogue_event = DialogueEvent.from_dict(payload.get("dialogue_event") or {})
        response_meta = ResponseMeta.from_dict(payload.get("response_meta") or {})
        if response_meta.event_id != dialogue_event.event_id:
            raise SchemaValidationError("dialogue_event.event_id must equal response_meta.event_id")
        return cls(
            dialogue_event=dialogue_event,
            response_meta=response_meta,
            metadata=Metadata.from_dict(payload.get("metadata")),
        )


@dataclass(slots=True)
class EstimatedPersona:
    """Temporary estimated persona, not a source M9 field."""

    personality_openness: float
    personality_conscientiousness: float
    personality_extraversion: float
    personality_agreeableness: float
    personality_neuroticism: float
    note: str = "心理模型临时评分结果，不是《数据关系模型》M9 原字段"

    def to_dict(self) -> dict[str, Any]:
        return {
            "personality_openness": round(self.personality_openness, 2),
            "personality_conscientiousness": round(self.personality_conscientiousness, 2),
            "personality_extraversion": round(self.personality_extraversion, 2),
            "personality_agreeableness": round(self.personality_agreeableness, 2),
            "personality_neuroticism": round(self.personality_neuroticism, 2),
            "note": self.note,
        }


@dataclass(slots=True)
class Feedback:
    game_id: str
    round_id: int
    actor_id: str = DEFAULT_ACTOR_ID
    satisfaction_change: int = 0
    skill_change: int = 0
    openness_change: int = 0
    conscientiousness_change: int = 0
    extraversion_change: int = 0
    agreeableness_change: int = 0
    neuroticism_change: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "round_id": self.round_id,
            "actor_id": self.actor_id,
            "satisfaction_change": self.satisfaction_change,
            "skill_change": self.skill_change,
            "openness_change": self.openness_change,
            "conscientiousness_change": self.conscientiousness_change,
            "extraversion_change": self.extraversion_change,
            "agreeableness_change": self.agreeableness_change,
            "neuroticism_change": self.neuroticism_change,
        }

@dataclass(slots=True)
class Evidence:
    """Structured behavior evidence used by report and LLM scoring."""

    trait: str
    quote: str
    reason: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Evidence":
        return cls(
            trait=str(payload.get("trait") or "general"),
            quote=str(payload.get("quote") or ""),
            reason=str(payload.get("reason") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trait": self.trait,
            "quote": self.quote,
            "reason": self.reason,
        }

@dataclass(slots=True)
class ScoreResult:
    metadata: Metadata
    dialogue_event: DialogueEvent
    estimated_persona: EstimatedPersona
    feedback: Feedback
    decision_style: str
    evidence: list[Any]
    confidence: float
    scoring_method: str
    prompt_version: str | None = None
    model_version: str | None = None
    rule_result: dict[str, Any] | None = None
    llm_result: dict[str, Any] | None = None
    hybrid_result: dict[str, Any] | None = None
    final_result: dict[str, Any] | None = None
    scoring_trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {
            "metadata": self.metadata.to_dict(),
            "dialogue_event": self.dialogue_event.to_dict(),
            "estimated_persona": self.estimated_persona.to_dict(),
            "feedback": self.feedback.to_dict(),
            "decision_style": self.decision_style,
            "evidence": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.evidence
            ],
            "confidence": round(self.confidence, 2),
            "scoring_method": self.scoring_method,
            "prompt_version": self.prompt_version,
            "model_version": self.model_version,
        }
        if self.scoring_trace is not None:
            data["rule_result"] = self.rule_result
            data["llm_result"] = self.llm_result
            data["hybrid_result"] = self.hybrid_result
            data["final_result"] = self.final_result
            data["scoring_trace"] = self.scoring_trace
        else:
            if self.rule_result is not None:
                data["rule_result"] = self.rule_result
            if self.llm_result is not None:
                data["llm_result"] = self.llm_result
            if self.hybrid_result is not None:
                data["hybrid_result"] = self.hybrid_result
            if self.final_result is not None:
                data["final_result"] = self.final_result
        return data


@dataclass(slots=True)
class SessionReport:
    session_id: str | None
    event_count: int
    average_estimated_persona: dict[str, float]
    total_feedback: dict[str, int]
    evidence: list[Any]
    average_confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "event_count": self.event_count,
            "average_estimated_persona": self.average_estimated_persona,
            "total_feedback": self.total_feedback,
            "evidence": [
                item.to_dict() if hasattr(item, "to_dict") else item
                for item in self.evidence
            ],
            "average_confidence": round(self.average_confidence, 2),
        }
