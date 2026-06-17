# SCORING PIPELINE v0.4

本文档说明 `v04_events` 如何接入当前 `personality-model` 的 rule / llm / hybrid 评分流程。v0.4 只做事件评分，不训练 embedding，不默认调用真实 LLM，也不修改 `bear` / `newbear` 项目。

## 流程

```text
data/processed/v04_events.jsonl
  -> src/adapters/v04_event_adapter.py
  -> ScoreInput
  -> src/hybrid_scorer.py
  -> data/processed/v04_scored_events.jsonl
  -> scene/session aggregation
  -> profile smoothing
  -> BFI 验证
```

运行命令：

```bash
python3 scripts/score_v04_events.py \
  --input data/processed/v04_events.jsonl \
  --output data/processed/v04_scored_events.jsonl \
  --method hybrid
```

默认 `--use-llm` 为 false，所以不会调用真实 LLM。`hybrid` 在未启用 LLM 时会 fallback 到 rule result。

## Adapter 结构

统一的是 `ScoreInput` 输出结构，不是输入数据结构。

- `src/adapters/common.py` 提供 `build_score_input_from_payload(metadata, dialogue_event, response_meta)`，最终统一调用 `ScoreInput.from_dict(payload)`。
- `src/adapters/v04_event_adapter.py` 面向 demo02 当前的 `v04_events.jsonl`。
- `src/adapters/newbear_adapter.py` 保留 `build_score_input_from_world(...)`，面向未来迁移 `bear` / `newbear`，但不依赖 newbear 的强类型，也不让 demo02 scoring 脚本依赖 newbear world。

## v04 Event 到 ScoreInput 的映射

`metadata`：

- `session_id = event["session_id"]`
- `user_id = event["user_id"]`
- `scene_name = event["scene_name"]`
- `timestamp = event["created_at"]`
- `extra` 包含 `participant_id`、`scene_id`、`task_id`、`task_name`、`target_traits`、`event_type`、`is_valid_event`、`quality_flags`

`dialogue_event`：

- `event_id = event["event_id"]`
- `game_id = event["session_id"]`
- `round_id = task_id * 2 - 1` for `main_answer`
- `round_id = task_id * 2` for `followup_answer`
- `npc_role = "情境任务"`
- `trigger_condition` 保留 scene/task/trait/event_type
- `npc_dialogue_script = event["prompt"]`
- `user_response_type = "FreeText"`

`response_meta`：

- `event_id = event["event_id"]`
- `user_free_text_input = event["user_text"]`
- `user_selected_option = None`
- `response_time_ms = None`

Adapter 不因为空文本或 invalid event 报错；这些事件由 scoring 脚本处理。

## Scored Events 字段

`v04_scored_events.jsonl` 每行保留原始 event 字段，并追加：

| 字段 | 说明 |
| --- | --- |
| `scored` | 是否实际调用评分器 |
| `skip_reason` | 未评分原因，通常来自 `quality_flags` |
| `rule_result` | rule scorer 摘要 |
| `llm_result` | LLM scorer 摘要，默认为空 |
| `hybrid_result` | hybrid scorer 摘要，仅真实 LLM 成功时非空 |
| `final_result` | 本轮最终评分结果 |
| `confidence` | 最终置信度 |
| `evidence` | 评分证据 |
| `decision_style` | 决策风格 |
| `scoring_method` | 实际最终评分方法 |
| `scoring_trace` | LLM 是否启用、是否使用、fallback 原因 |

同时生成：

- `v04_scored_events.csv`
- `v04_scoring_report.json`

## Invalid / Low Quality Event

默认 `--include-invalid=true`。当 `is_valid_event=false` 时，脚本仍输出一行，但：

- `scored=false`
- `skip_reason` 写入 `quality_flags`
- 不调用 rule / llm / hybrid 评分器
- `rule_result`、`llm_result`、`hybrid_result`、`final_result` 为空

如果传入 `--no-include-invalid`，invalid event 不写入 scored_events，但仍计入 report 的 `skipped_event_count`。

## LLM 默认关闭

`scripts/score_v04_events.py` 的 `--use-llm` 默认 false。即使使用 `--method hybrid`，默认也不会调用真实 LLM API；输出中的 `scoring_trace.fallback_reason` 通常为 `LLM_NOT_REQUESTED` 或环境侧的 `LLM_DISABLED`。

只有显式传入 `--use-llm`，且环境配置允许时，才会尝试调用现有 LLM scorer。
