# personality-model

独立的“熊起”心理模型评分模块第一版。项目只做：

```text
M6 dialogue_event + M7 response_meta + metadata
-> estimated_persona 本轮临时人格估计
-> M9 feedback 变化量
-> scored_events.jsonl
```

本模块不改主游戏项目、不接真实数据库、不调用真实 API Key。

## 字段边界

- `dialogue_event` 对齐 M6 互动单元。
- `response_meta` 对齐 M7 用户回应数据采集。
- `feedback` 对齐 M9 反馈回路，用户测评第一版中 `actor_id` 固定为 `玩家`。
- `estimated_persona` 是心理模型临时评分结果，不是 M9 原字段。
- `metadata` 可包含 `session_id / user_id / scene_name / timestamp`，只用于 CLI 演示、导出和后续 BFI 对照，不属于 M1-M9 正式业务字段。
- M6 的 `npc_role` 只是发起对话的 NPC，不是被评分对象。

## Neuroticism 方向

`personality_neuroticism` 固定解释为：越高 = 越焦虑、越压力敏感、越情绪不稳定。

如果前端后续展示“情绪稳定性”，必须使用：

```text
emotional_stability = 100 - personality_neuroticism
```

## 运行

```bash
python -m pytest
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events.jsonl
```

CLI 会把每轮评分写入 `data/outputs/scored_events.jsonl`，并在终端打印 session 汇总。

## 注意

规则评分是启发式 baseline，用于比赛稿原型和后续验证，不是心理诊断，也不是最终心理测量结论。

