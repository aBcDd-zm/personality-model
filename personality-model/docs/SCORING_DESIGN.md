# 评分设计

## 目标

第一版实现从 M6 事件情境与 M7 用户回应到临时人格估计和 M9 feedback 的最小闭环。

```text
dialogue_event + response_meta
-> estimated_persona
-> feedback
```

`estimated_persona` 是临时评分结果，`feedback` 才是严格对应 M9 的变化量字段。

## 大五人格方向

- 开放性：高分表示愿意尝试新方案、接受变化、提出创新路径。
- 尽责性：高分表示重视质量、计划、交付、责任和复盘。
- 外倾性：高分表示主动沟通、表达立场、推动讨论。
- 宜人性：高分表示关注合作、共情、安抚、协调冲突。
- 神经质：越高 = 越焦虑、越压力敏感、越情绪不稳定。

如果前端展示“情绪稳定性”，需要用：

```text
情绪稳定性 = 100 - personality_neuroticism
```

## 决策风格

- `rational`：关注逻辑、数据、风险、优先级和方案。
- `empathetic`：关注他人感受、合作关系和团队氛围。
- `assertive`：主动推动、明确表态、争取资源。
- `avoidant`：回避冲突、模糊表达或拖延选择。

## 规则 baseline

规则评分是启发式 baseline，不是心理诊断，也不是最终心理测量结论。

第一版规则包括：

- 对 M7 文本补齐长度、情绪、词汇丰富度、第一人称占比。
- 按《数据关系模型》4.4 的 M7 -> M3 思路估计五维人格。
- 使用关键词规则补充 evidence 和 decision style。
- 根据临时分数生成 M9 `feedback` 变化量。
- 用户测评第一版中 `feedback.actor_id` 固定为 `玩家`。

## Zero-shot LLM

`llm_prompt.py` 提供 zero-shot prompt，`llm_scorer.py` 通过 OpenAI SDK 兼容方式调用 DeepSeek。默认 `LLM_ENABLED=false`，不会调用真实 API。

Prompt 要求模型：

- 评分对象永远是玩家。
- NPC 角色和 NPC 台词只作为情境背景。
- 证据必须来自用户自由文本或用户选择的选项。
- 不根据 NPC 台词本身判断玩家人格。
- 只根据本轮证据评分。
- 输出纯 JSON。
- 不做医学诊断。
- 不判断人格障碍。
- 每个分数在 0-100。
- 必须给出行为证据和置信度。
- `decision_style` 只能是 `rational`、`empathetic`、`assertive`、`avoidant`、`balanced`、`unclear`。

LLM 输出会被二次校验：

- 五维人格分数 clamp 到 0-100。
- LLM confidence clamp 到 0-0.75，避免单轮 LLM 判断过度自信。
- evidence 统一为 `{trait, quote, reason}`。
- API 失败、无 Key、JSON 解析失败时返回 `None`。

## Hybrid

有 LLM 结果时使用：

```text
hybrid_score = 0.4 * rule_score + 0.6 * llm_score
```

Hybrid 的 `confidence` 先按 `0.4 * rule_confidence + 0.6 * llm_confidence` 合成，再根据 rule 和 LLM 五维分数的平均差异调整：

- 差异较小时提高 confidence，表示两个评分器互相印证。
- 差异较大时降低 confidence，表示当前事件证据存在解释分歧。

没有 LLM 结果时回退到规则 baseline，`final_result = rule_result`，并在 `scoring_trace.fallback_reason` 中记录原因。
