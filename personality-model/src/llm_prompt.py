from __future__ import annotations

import json

from .schemas import ScoreInput


PROMPT_VERSION = "zero_shot_v1"


def build_zero_shot_prompt(score_input: ScoreInput) -> str:
    payload = {
        "dialogue_event": score_input.dialogue_event.to_dict(),
        "response_meta": score_input.response_meta.to_dict(),
        "metadata": score_input.metadata.to_dict(),
    }
    return (
        "你是一个游戏化职场人格测评评分器。只根据本轮 M6 dialogue_event 和 "
        "M7 response_meta 的证据做临时评分，不做医学诊断，不判断人格障碍。\n"
        "neuroticism 方向固定为：越高 = 越焦虑、越压力敏感、越情绪不稳定；"
        "若展示情绪稳定性，应使用 100 - neuroticism。\n"
        "M6 npc_role 只是发起对话的 NPC，评分对象固定为 M9 actor_id=玩家。\n"
        "输出必须是纯 JSON，不要夹杂自然语言。分数范围均为 0-100。\n"
        "JSON schema:\n"
        "{\n"
        '  "estimated_persona": {\n'
        '    "personality_openness": 0,\n'
        '    "personality_conscientiousness": 0,\n'
        '    "personality_extraversion": 0,\n'
        '    "personality_agreeableness": 0,\n'
        '    "personality_neuroticism": 0\n'
        "  },\n"
        '  "decision_style": "rational|empathetic|assertive|avoidant",\n'
        '  "evidence": ["行为证据"],\n'
        '  "confidence": 0.7\n'
        "}\n"
        f"本轮输入：\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

