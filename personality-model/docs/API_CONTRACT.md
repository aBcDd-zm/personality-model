# API 契约草案

## POST /score/event

单事件评分。

### Request

```json
{
  "metadata": {
    "session_id": "S001",
    "user_id": "U001",
    "scene_name": "会议室",
    "timestamp": "2026-06-06T10:00:00"
  },
  "dialogue_event": {
    "event_id": "EV_001",
    "game_id": "G001",
    "round_id": 1,
    "npc_role": "熊老板",
    "trigger_condition": {"time_pressure_level": 8},
    "npc_dialogue_script": "这个版本今天必须上线，你打算怎么处理？",
    "user_response_type": "FreeText"
  },
  "response_meta": {
    "event_id": "EV_001",
    "user_free_text_input": "我建议先确认最关键的功能，低风险部分今天上线，高风险问题先标记出来，避免为了赶进度影响质量。",
    "user_selected_option": null,
    "response_time_ms": 15000
  }
}
```

### Response

```json
{
  "metadata": {},
  "dialogue_event": {},
  "estimated_persona": {
    "personality_openness": 72,
    "personality_conscientiousness": 81,
    "personality_extraversion": 48,
    "personality_agreeableness": 70,
    "personality_neuroticism": 22,
    "note": "心理模型临时评分结果，不是《数据关系模型》M9 原字段"
  },
  "feedback": {
    "game_id": "G001",
    "round_id": 1,
    "actor_id": "玩家",
    "satisfaction_change": 0,
    "skill_change": 0,
    "openness_change": 1,
    "conscientiousness_change": 2,
    "extraversion_change": 0,
    "agreeableness_change": 1,
    "neuroticism_change": -1
  },
  "decision_style": "rational",
  "evidence": ["用户优先拆分风险并保证交付质量。"],
  "confidence": 0.72,
  "scoring_method": "rule",
  "prompt_version": "rule_baseline_v1",
  "model_version": null
}
```

## POST /score/session

多事件批量评分与汇总。

### Request

```json
{
  "events": [
    {
      "metadata": {},
      "dialogue_event": {},
      "response_meta": {}
    }
  ]
}
```

### Response

```json
{
  "events": [],
  "session_report": {
    "session_id": "S001",
    "event_count": 6,
    "average_estimated_persona": {},
    "total_feedback": {},
    "evidence": [],
    "average_confidence": 0.7
  }
}
```

## 前台暴露边界

前台只应看到 NPC 台词、作答入口和业务反馈。M7 采集指标、M9 变化量、权重公式和人格中间分应作为后台数据保存，避免用户迎合测量逻辑。

