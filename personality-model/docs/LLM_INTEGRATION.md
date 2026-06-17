# LLM zero-shot 接入说明

## 为什么接 LLM

v0.1/v0.2 的 `rule_baseline` 可以稳定、透明地给出最低可用评分，但它主要依赖文本特征和关键词，难以理解更复杂的表达策略。v0.3 增加 LLM zero-shot scoring，用来补充对玩家自由文本的语义判断。

LLM 结果不是替代规则 baseline，而是作为可选增强；当 LLM 不可用时系统仍回退到规则评分。

## 输入

LLM 输入只包含当前事件的：

- M6 `dialogue_event`
- M7 `response_meta`
- 可选 `metadata`

`npc_role`、`npc_dialogue_script` 和 `trigger_condition` 只作为情境背景。人格证据必须来自 `response_meta.user_free_text_input` 或 `response_meta.user_selected_option`。

## 输出

LLM 输出会被归一化为：

- `estimated_persona`：五维人格临时分数，范围 0-100
- `decision_style`：`rational` / `empathetic` / `assertive` / `avoidant` / `balanced` / `unclear`
- `evidence`：数组，每条包含 `trait`、`quote`、`reason`
- `confidence`：范围 0-0.75
- `prompt_version`
- `model_version`

## 配置 API Key

复制 `.env.example` 为 `.env`，并填写：

```bash
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
LLM_ENABLED=true
LLM_TIMEOUT_SECONDS=30
```

`.env` 已加入 `.gitignore`，不要把真实 API Key 写入代码、文档、测试数据或日志。

## 为什么默认关闭

默认 `LLM_ENABLED=false`，原因是：

- 本地测试和 CI 不应该依赖外部 API。
- 没有 API Key 时仍要可复现运行。
- LLM 输出有不确定性，需要显式开启后才参与评分。

## fallback 设计

以下情况都会返回 `None` 并回退到 `rule_baseline`：

- `LLM_ENABLED=false`
- 缺少 `DEEPSEEK_API_KEY`
- OpenAI SDK 不可用
- DeepSeek API 请求失败或超时
- LLM 返回内容不是合法 JSON
- JSON 缺少必要字段

CLI 输出的 `scoring_trace` 会记录 `llm_enabled`、`llm_used` 和 `fallback_reason`。

## 不是心理诊断

本项目的 LLM 评分只根据当前游戏事件中的玩家回应做临时行为画像，不是医学或心理诊断，不判断人格障碍，也不能代表长期稳定人格。

## CLI 示例

规则 baseline：

```bash
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events_rule.jsonl --method rule
```

Hybrid + LLM 请求：

```bash
python -m src.cli --input data/examples/sample_events.jsonl --output data/outputs/scored_events_hybrid.jsonl --method hybrid --use-llm
```

如果没有 API Key 或 `LLM_ENABLED=false`，第二条命令也会完成，只是 `final_result` 会等于 `rule_result`，`scoring_trace.fallback_reason` 会说明原因。
