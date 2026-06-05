# 字段说明

## 正式业务字段边界

第一版只使用《数据关系模型》中的 M6、M7、M9 字段完成用户测评闭环，不新增 M1-M9 业务字段。

`session_id / user_id / scene_name / timestamp` 可放入 `metadata`，用于 CLI 演示、导出数据和后续 BFI 问卷对照，但不属于 M1-M9 正式字段。

## M6 dialogue_event

后端需要提供：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `event_id` | 是 | 事件唯一标识，串联 M6 与 M7 |
| `game_id` | 是 | 对局 ID |
| `round_id` | 是 | 回合 ID，必须是整数 |
| `npc_role` | 是 | 发起对话的 NPC，不是评分对象 |
| `trigger_condition` | 否 | 触发条件，后台字段 |
| `npc_dialogue_script` | 是 | NPC 台词 |
| `user_response_type` | 是 | `FreeText / Option / Action` |

## M7 response_meta

后端或本模块需要提供：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `event_id` | 是 | 必须等于 M6 `event_id` |
| `user_free_text_input` | 否 | 用户自由文本 |
| `user_selected_option` | 否 | 用户选择的预设选项 |
| `response_time_ms` | 否 | 输入耗时 |
| `response_length` | 否 | 可由模块后处理 |
| `response_sentiment` | 否 | 可由模块用启发式规则估算 |
| `response_lexical_diversity` | 否 | 可由模块后处理 |
| `response_self_focus_ratio` | 否 | 可由模块后处理 |

只有选项、没有自由文本时可以评分；空文本和超时不作答也必须返回安全默认值。

## estimated_persona

`estimated_persona` 是本轮心理模型临时估计的人格画像，不是 M9 原字段。

包含：

- `personality_openness`
- `personality_conscientiousness`
- `personality_extraversion`
- `personality_agreeableness`
- `personality_neuroticism`

## M9 feedback

严格对应 M9 的输出字段在 `feedback` 中：

- `game_id`
- `round_id`
- `actor_id`：用户测评第一版固定为 `玩家`
- `satisfaction_change`
- `skill_change`
- `openness_change`
- `conscientiousness_change`
- `extraversion_change`
- `agreeableness_change`
- `neuroticism_change`

