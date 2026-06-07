# personality-model 前后端对接说明 v0.3

本文用于前端、后端、报告页与心理评分模块的联调。重点说明输入字段、输出字段、`final_result` 使用规则、M9 写回方式、LLM fallback 行为和接口包装建议。

## 1. 当前结论

- 当前仓库已经完成本地评分模块，不是完整 Web 服务。
- 已有能力：`rule_baseline`、`llm_zero_shot`、`hybrid`、结构化 `evidence`、`final_result`、`scoring_trace`。
- 后端对接时应把本模块包装成 HTTP 接口，例如 `POST /score/event` 和 `POST /score/session`。
- 前端和报告页优先读取 `final_result`，不要直接依赖 `rule_result`、`llm_result`、`hybrid_result`。
- M9 写回只使用 `final_result.feedback`，不要把 `estimated_persona` 的 0-100 分数直接写入 M9。
- LLM 不可用时不是接口错误，系统会 fallback 到 `rule_baseline`，并在 `scoring_trace.fallback_reason` 中说明原因。

## 2. 模块边界

```text
M6 dialogue_event + M7 response_meta + metadata
-> personality-model scoring
-> rule_result / llm_result / hybrid_result
-> final_result
-> M9 feedback + report evidence
```

本模块负责把一轮游戏事件和玩家回应转换为结构化评分结果。它不负责生成剧情、不直接改主游戏数据库、不在前端暴露评分公式。

## 3. 推荐接口

### 3.1 POST /score/event

用途：对单轮事件评分，返回本轮最终评分结果。

请求约定：

- Method: `POST`
- Content-Type: `application/json`
- Body: `metadata + dialogue_event + response_meta`

#### Request 示例

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
    "trigger_condition": {
      "time_pressure_level": 8
    },
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

#### Response 示例

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
    "trigger_condition": {
      "time_pressure_level": 8
    },
    "npc_dialogue_script": "这个版本今天必须上线，你打算怎么处理？",
    "user_response_type": "FreeText"
  },
  "estimated_persona": {
    "personality_openness": 64.94,
    "personality_conscientiousness": 97.95,
    "personality_extraversion": 10.52,
    "personality_agreeableness": 99.12,
    "personality_neuroticism": 10.0,
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
    "extraversion_change": -2,
    "agreeableness_change": 2,
    "neuroticism_change": -2
  },
  "decision_style": "rational",
  "evidence": [
    {
      "trait": "personality_conscientiousness",
      "quote": "我建议先确认最关键的功能，低风险部分今天上线，高风险问题先标记出来，避免为了赶进度影响质量。",
      "reason": "用户提到质量、计划、交付、确认或风险控制，体现尽责倾向。"
    }
  ],
  "confidence": 0.63,
  "scoring_method": "rule_baseline",
  "prompt_version": "rule_baseline_v1",
  "model_version": null,
  "rule_result": {
    "estimated_persona": {
      "personality_openness": 64.94,
      "personality_conscientiousness": 97.95,
      "personality_extraversion": 10.52,
      "personality_agreeableness": 99.12,
      "personality_neuroticism": 10.0,
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
      "extraversion_change": -2,
      "agreeableness_change": 2,
      "neuroticism_change": -2
    },
    "decision_style": "rational",
    "evidence": [
      {
        "trait": "personality_conscientiousness",
        "quote": "我建议先确认最关键的功能，低风险部分今天上线，高风险问题先标记出来，避免为了赶进度影响质量。",
        "reason": "用户提到质量、计划、交付、确认或风险控制，体现尽责倾向。"
      }
    ],
    "confidence": 0.63,
    "scoring_method": "rule_baseline",
    "prompt_version": "rule_baseline_v1",
    "model_version": null
  },
  "llm_result": null,
  "hybrid_result": null,
  "final_result": {
    "estimated_persona": {
      "personality_openness": 64.94,
      "personality_conscientiousness": 97.95,
      "personality_extraversion": 10.52,
      "personality_agreeableness": 99.12,
      "personality_neuroticism": 10.0,
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
      "extraversion_change": -2,
      "agreeableness_change": 2,
      "neuroticism_change": -2
    },
    "decision_style": "rational",
    "evidence": [
      {
        "trait": "personality_conscientiousness",
        "quote": "我建议先确认最关键的功能，低风险部分今天上线，高风险问题先标记出来，避免为了赶进度影响质量。",
        "reason": "用户提到质量、计划、交付、确认或风险控制，体现尽责倾向。"
      }
    ],
    "confidence": 0.63,
    "scoring_method": "rule_baseline",
    "prompt_version": "rule_baseline_v1",
    "model_version": null
  },
  "scoring_trace": {
    "llm_enabled": false,
    "llm_used": false,
    "fallback_reason": "LLM_DISABLED"
  }
}
```

### 3.2 POST /score/session

用途：对同一 session 的多轮事件批量评分，并返回 session 汇总。

请求约定：

- Method: `POST`
- Content-Type: `application/json`
- Body: `{ "events": [ScoreEventRequest] }`

#### Request 示例

```json
{
  "events": [
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
        "trigger_condition": {
          "time_pressure_level": 8
        },
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
  ]
}
```

#### Response 示例

```json
{
  "events": [
    {
      "event_id": "EV_001",
      "final_result": {
        "feedback": {
          "game_id": "G001",
          "round_id": 1,
          "actor_id": "玩家",
          "satisfaction_change": 0,
          "skill_change": 0,
          "openness_change": 1,
          "conscientiousness_change": 2,
          "extraversion_change": -2,
          "agreeableness_change": 2,
          "neuroticism_change": -2
        },
        "decision_style": "rational",
        "confidence": 0.63,
        "scoring_method": "rule_baseline"
      },
      "scoring_trace": {
        "llm_enabled": false,
        "llm_used": false,
        "fallback_reason": "LLM_DISABLED"
      }
    }
  ],
  "session_report": {
    "session_id": "S001",
    "event_count": 1,
    "average_estimated_persona": {
      "personality_openness": 64.94,
      "personality_conscientiousness": 97.95,
      "personality_extraversion": 10.52,
      "personality_agreeableness": 99.12,
      "personality_neuroticism": 10.0
    },
    "total_feedback": {
      "openness_change": 1,
      "conscientiousness_change": 2,
      "extraversion_change": -2,
      "agreeableness_change": 2,
      "neuroticism_change": -2
    },
    "evidence": [
      {
        "trait": "personality_conscientiousness",
        "quote": "我建议先确认最关键的功能，低风险部分今天上线，高风险问题先标记出来，避免为了赶进度影响质量。",
        "reason": "用户提到质量、计划、交付、确认或风险控制，体现尽责倾向。"
      }
    ],
    "average_confidence": 0.63
  }
}
```

说明：当前 CLI 的 session 汇总会打印 `session_report`，如果后端实现 `/score/session`，建议同时返回每个 event 的简版评分结果和汇总结果，方便调试与报告页使用。

## 4. 输入字段说明

### 4.1 metadata

`metadata` 是辅助信息，不属于正式 M1-M9 业务字段。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 否 | 一次游戏或测评会话 ID，用于 session 汇总 |
| `user_id` | string | 否 | 用户 ID，用于样本匹配 |
| `scene_name` | string | 否 | 当前场景名 |
| `timestamp` | string | 否 | 事件时间，建议 ISO 8601 |
| 其他字段 | any | 否 | 会被保留到 `metadata` 输出中 |

### 4.2 dialogue_event

`dialogue_event` 对齐 M6 互动事件。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `event_id` | string | 是 | 本轮事件 ID，必须等于 `response_meta.event_id` |
| `game_id` | string | 是 | 游戏或测评 ID |
| `round_id` | integer | 是 | 当前轮次 |
| `npc_role` | string | 是 | 发起对话的 NPC，不是评分对象 |
| `trigger_condition` | object/null | 否 | 当前事件触发条件，作为评分上下文 |
| `npc_dialogue_script` | string | 否 | NPC 台词，可为空字符串 |
| `user_response_type` | enum | 是 | `FreeText` / `Option` / `Action` |

### 4.3 response_meta

`response_meta` 对齐 M7 用户回应数据。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `event_id` | string | 是 | 必须等于 `dialogue_event.event_id` |
| `user_free_text_input` | string/null | 条件必填 | `FreeText` 时建议必填；自由文本证据主要来自这里 |
| `user_selected_option` | integer/null | 条件必填 | `Option` 时建议必填 |
| `response_time_ms` | integer/null | 否 | 用户响应耗时，建议保留 |
| `response_length` | integer/null | 否 | 后端不传时，模型模块可后处理补齐 |
| `response_sentiment` | number/null | 否 | 建议范围 `-1` 到 `1`，后端不传时可后处理 |
| `response_lexical_diversity` | number/null | 否 | 词汇多样性，后端不传时可后处理 |
| `response_self_focus_ratio` | number/null | 否 | 自我关注比例，后端不传时可后处理 |

## 5. 输出字段说明

### 5.1 顶层兼容字段

当前输出保留旧版顶层字段，方便已有脚本继续运行：

| 字段 | 说明 |
| --- | --- |
| `metadata` | 原样保留输入中的辅助信息 |
| `dialogue_event` | 原样保留输入中的 M6 事件 |
| `estimated_persona` | 本轮临时五维人格分数，范围 0-100，不是 M9 原字段 |
| `feedback` | 可写回 M9 的变化量 |
| `decision_style` | 本轮决策风格 |
| `evidence` | 结构化证据数组 |
| `confidence` | 本轮评分置信度 |
| `scoring_method` | 本轮顶层采用的方法 |
| `prompt_version` | 规则或 LLM prompt 版本 |
| `model_version` | LLM 模型名；规则评分为 `null` |

### 5.2 v0.3 分层字段

| 字段 | 说明 | 前后端使用建议 |
| --- | --- | --- |
| `rule_result` | 规则 baseline 结果 | 后端调试可看，不给前端展示 |
| `llm_result` | LLM zero-shot 结果；未启用或失败时为 `null` | 后端调试可看，不给前端展示 |
| `hybrid_result` | 规则和 LLM 融合结果；未融合时为 `null` | 后端调试可看，不给前端展示 |
| `final_result` | 本轮最终采用结果 | 后端、报告页、M9 写回优先使用 |
| `scoring_trace` | LLM 启用、使用和 fallback 记录 | 后端调试使用，不给前端展示 |

### 5.3 final_result 内部字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `estimated_persona` | object | 五维人格临时评分，范围 0-100 |
| `feedback` | object | M9 写回变化量 |
| `decision_style` | enum | `rational` / `empathetic` / `assertive` / `avoidant` / `balanced` / `unclear` |
| `evidence` | array | 每项包含 `trait`、`quote`、`reason` |
| `confidence` | number | 置信度；规则最高 0.9，LLM 单独结果最高 0.75 |
| `scoring_method` | string | `rule_baseline` / `llm_zero_shot` / `hybrid` |
| `prompt_version` | string/null | prompt 或规则版本 |
| `model_version` | string/null | LLM 模型名 |

## 6. M9 写回规则

后端写回 M9 时只读取：

```text
final_result.feedback
```

不要写入：

```text
final_result.estimated_persona
rule_result
llm_result
hybrid_result
scoring_trace
```

### 6.1 feedback 字段

| 字段 | 类型 | 当前范围 | 说明 |
| --- | --- | --- | --- |
| `game_id` | string | - | 对应 M6 输入的 `game_id` |
| `round_id` | integer | - | 对应 M6 输入的 `round_id` |
| `actor_id` | string | 固定为 `玩家` | 当前版本评分对象固定为玩家 |
| `satisfaction_change` | integer | 当前固定 0 | 预留字段 |
| `skill_change` | integer | 当前固定 0 | 预留字段 |
| `openness_change` | integer | -2 到 2 | 开放性变化量 |
| `conscientiousness_change` | integer | -2 到 2 | 尽责性变化量 |
| `extraversion_change` | integer | -2 到 2 | 外倾性变化量 |
| `agreeableness_change` | integer | -2 到 2 | 宜人性变化量 |
| `neuroticism_change` | integer | -2 到 2 | 神经质变化量 |

### 6.2 当前变化量换算

当前代码把五维人格 0-100 临时分数转换为 M9 变化量：

| 临时分数区间 | change |
| --- | --- |
| `score >= 75` | `+2` |
| `60 <= score < 75` | `+1` |
| `40 < score < 60` | `0` |
| `25 < score <= 40` | `-1` |
| `score <= 25` | `-2` |

session 级 M9 汇总建议按字段求和：

```text
session_total.openness_change = sum(event.final_result.feedback.openness_change)
```

## 7. LLM 与 fallback

### 7.1 环境变量

复制 `.env.example` 为 `.env`，本地或服务端自行配置：

```bash
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_ENABLED=true
LLM_TIMEOUT_SECONDS=30
```

安全要求：

- `.env` 不提交 Git。
- API key 不写入代码、文档、测试数据、日志。
- CI 和本地普通测试默认 `LLM_ENABLED=false`。

### 7.2 fallback_reason

| 值 | 含义 | 是否应中断接口 |
| --- | --- | --- |
| `METHOD_RULE` | 请求方法为 rule，只跑规则评分 | 否 |
| `LLM_NOT_REQUESTED` | 没有请求使用 LLM | 否 |
| `LLM_DISABLED` | 环境变量未启用 LLM | 否 |
| `MISSING_API_KEY` | 缺少 DeepSeek API key | 否 |
| `LLM_ERROR` | LLM 请求失败、超时或返回非法 JSON | 否 |
| `null` | LLM 成功使用 | 否 |

只要 `final_result` 存在，后端就可以继续写回 M9 或生成报告。

## 8. 错误响应建议

当前仓库是本地模块，HTTP 错误格式需要后端包装层实现。建议统一为：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "dialogue_event.event_id must equal response_meta.event_id",
    "field": "response_meta.event_id",
    "details": {}
  }
}
```

推荐状态码：

| HTTP 状态码 | code | 场景 |
| --- | --- | --- |
| `400` | `INVALID_JSON` | 请求体不是合法 JSON |
| `400` | `VALIDATION_ERROR` | 缺少必填字段、类型错误、`event_id` 不一致 |
| `422` | `UNSUPPORTED_RESPONSE_TYPE` | `user_response_type` 不在允许枚举内 |
| `500` | `SCORING_ERROR` | 模块内部异常且无法生成 `final_result` |

LLM 不可用不建议返回 5xx，因为当前设计会 fallback 到规则评分。

## 9. 前端展示边界

前端可以展示：

- NPC 台词和玩家作答入口。
- 报告页经过产品化处理后的性格倾向、决策风格、证据引用。
- 必要时展示 `final_result.evidence.quote` 和产品化后的 `reason`。

前端不建议展示：

- M7 原始采集特征，如 `response_time_ms`、`response_lexical_diversity`。
- `rule_result`、`llm_result`、`hybrid_result`。
- `scoring_trace`。
- 权重公式，如 `0.4 * rule_score + 0.6 * llm_score`。
- 原始 0-100 人格中间分，除非产品明确要做报告页并经过解释包装。

特别注意：`personality_neuroticism` 越高表示越焦虑、越压力敏感、越情绪不稳定。如果前端要展示“情绪稳定性”，必须转换：

```text
emotional_stability = 100 - personality_neuroticism
```

## 10. 后端联调步骤

1. 确认主项目字段名是否能映射到 `metadata + dialogue_event + response_meta`。
2. 封装 `POST /score/event`，内部调用 `ScoreInput.from_dict()` 和 `score()`。
3. 将 `SchemaValidationError` 映射为 `400 VALIDATION_ERROR`。
4. 默认先用 `method=hybrid`、`use_llm=false` 或环境 `LLM_ENABLED=false` 跑通规则 fallback。
5. 联调确认 `final_result.feedback` 可写回 M9。
6. 再开启 `LLM_ENABLED=true` 和 `--use-llm` 等价逻辑验证 LLM 路径。
7. 封装 `POST /score/session`，返回每轮结果和 `session_report`。
8. 确认日志不输出 API key，不把 `.env`、`data/outputs/` 提交到仓库。

## 11. 本地验证命令

在 `personality-model` 目录下执行：

```bash
python -m pytest
```

规则 baseline：

```bash
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events_rule.jsonl --method rule
```

Hybrid，但不请求 LLM：

```bash
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events_hybrid.jsonl --method hybrid
```

Hybrid，并请求 LLM：

```bash
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events_hybrid.jsonl --method hybrid --use-llm
```

如果没有配置 API key 或 `LLM_ENABLED=false`，最后一条命令也会完成，只是 `final_result` 会等于 `rule_result`。

## 12. 对接验收清单

- [ ] `/score/event` 能接受完整示例请求并返回 `final_result`。
- [ ] `dialogue_event.event_id != response_meta.event_id` 时返回校验错误。
- [ ] LLM 关闭时接口不中断，`final_result == rule_result`。
- [ ] LLM 成功时 `final_result.scoring_method == "hybrid"` 或 `"llm_zero_shot"`。
- [ ] M9 只写入 `final_result.feedback`。
- [ ] 前端不展示 `scoring_trace`、中间分、权重公式。
- [ ] 报告页引用 `evidence` 时保留 `quote` 和解释口径。
- [ ] `.env`、API key、`data/outputs/` 不提交仓库。

