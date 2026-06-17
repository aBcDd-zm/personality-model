# DATA_SCHEMA v0.4

本文档定义 `scripts/convert_raw_dataset_v04.py` 从原始导出 CSV 生成的标准数据格式。v0.4 只做离线数据转换，不连接真实 LLM API，不训练模型，也不改 `bear` / `newbear` 主项目。

## 输入

默认输入：

```bash
data/raw/personality_dataset_20260609_143645.csv
```

如果默认路径不存在，可以显式传入任意 CSV：

```bash
python scripts/convert_raw_dataset_v04.py --input path/to/input.csv --output-dir data/processed
```

输入 CSV 使用当前导出的宽表结构：每一行代表一个 `participant_id` 在一个 `task_id` / `task_name` 情境模块中的回答记录，并包含 BFI-2-S 问卷标签、主问题回答和追问回答。

## 输出

脚本输出到 `data/processed/`：

- `v04_events.jsonl`
- `v04_events.csv`
- `v04_sessions.jsonl`
- `v04_sessions.csv`
- `v04_labels.jsonl`
- `v04_labels.csv`
- `v04_quality_report.json`

JSONL 用于后续程序读取，CSV 用于人工检查和轻量分析。

## v0.4 口径

- 问卷版本：`BFI-2-S`
- `event`：玩家每次回答。当前每行拆成 `main_answer` 和 `followup_answer` 两个 event。
- `scene`：一个情境模块。当前每个 `task_id` / `task_name` 是一个 scene。
- `session`：用户从开始测评到生成结果的完整流程。旧 CSV 没有 `session_id`，所以 `session_id = "S_" + participant_id`。
- `profile`：多次 session 之后的长期人格画像。v0.4 转换脚本不生成 profile。
- `confidence`：后续使用 0-1 分数。v0.4 转换脚本不计算 confidence。
- `scene_score` 和 `session_score`：后续使用 confidence 加权平均。
- `profile` 初始值：全部 50。
- 长期画像更新：`alpha = 0.2`。
- `confidence < 0.2` 的 event：只保留 evidence，不强参与画像更新。
- 第一版迁移范围：rule + llm + hybrid + scene/session aggregation + profile smoothing。
- embedding regression：留在 `demo02` 做实验，不直接进入 `bear` 主项目。

## Label 数据

每个 `participant_id` 生成一条 label/session 标签记录。

ID 规则：

- `user_id = participant_id`
- `session_id = "S_" + participant_id`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | string | 用户 ID，当前等于 `participant_id` |
| `session_id` | string | 当前由 participant 派生 |
| `participant_id` | string | 原始参与者 ID |
| `age_group` | string/null | 年龄段 |
| `gender` | string/null | 性别 |
| `education` | string/null | 教育背景 |
| `bfi_version` | string/null | 问卷版本，预期为 `BFI-2-S` |
| `bfi_q1` - `bfi_q30` | number/null | BFI-2-S 原始题项分 |
| `bfi_O_raw`, `bfi_C_raw`, `bfi_E_raw`, `bfi_A_raw`, `bfi_N_raw` | number/null | 五维原始分，统一按 O, C, E, A, N 排列 |
| `bfi_O_100`, `bfi_C_100`, `bfi_E_100`, `bfi_A_100`, `bfi_N_100` | number/null | 五维 0-100 分 |
| `facet_*_raw` | number/null | facet 原始分 |
| `facet_*_100` | number/null | facet 0-100 分 |

0-100 换算：

```text
score_100 = (score_raw - 1) / 4 * 100
```

空原始分输出 `null`。0-100 分保留两位小数。

## Event 数据

当前 CSV 每一行拆成两个 event：

- `event_type = main_answer`，对应 `prompt = main_prompt`，`user_text = user_answer_1`
- `event_type = followup_answer`，对应 `prompt = followup_prompt`，`user_text = user_answer_2`

ID 规则：

- `event_id = "EV_{participant_id}_T{task_id}_A1"`
- `event_id = "EV_{participant_id}_T{task_id}_A2"`
- `scene_id = "SCENE_T{task_id}"`
- `session_id = "S_" + participant_id`

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `event_id` | string | event 唯一 ID |
| `session_id` | string | session ID |
| `user_id` | string | 当前等于 `participant_id` |
| `participant_id` | string | 原始参与者 ID |
| `scene_id` | string | scene ID |
| `scene_name` | string/null | 当前等于 `task_name` |
| `task_id` | string | 原始任务 ID |
| `task_name` | string/null | 原始任务名称 |
| `target_traits` | string/null | 原始目标 trait 字段 |
| `event_type` | string | `main_answer` 或 `followup_answer` |
| `prompt` | string/null | 对应 prompt |
| `user_text` | string/null | 玩家回答 |
| `text_char_count` | integer | 回答字符数 |
| `quality_flag_raw` | string/null | 原始质量标记 |
| `quality_flags` | array/string | JSONL 中为数组，CSV 中用 `|` 连接 |
| `is_low_quality` | boolean | 是否低质量 |
| `is_valid_event` | boolean | 是否可用于后续强参与画像更新 |
| `created_at` | string/null | 原始创建时间 |

质量规则：

- 原始 `quality_flag == "low_quality"` 时，增加 `raw_low_quality`，`is_low_quality = true`。
- `user_text` 为空时，增加 `empty_text`，`is_low_quality = true`。
- `user_text` 去除空格后的长度小于 10 时，增加 `too_short`，`is_low_quality = true`。
- 回答中大量重复同一个字符时，增加 `repeated_chars`，`is_low_quality = true`。
- 回答和 prompt 高度重叠时，增加 `possible_prompt_copy`。该标记只提示风险，不直接删除。
- `is_valid_event = quality_flag_raw == "ok"`，且回答非空，且去空格后长度至少 10，且没有 `repeated_chars`。

`possible_prompt_copy` 使用简单规则：

- `user_text` 长度至少 30；
- 且 `user_text` 是 `prompt` 的连续子串，或 `difflib.SequenceMatcher` 相似度不小于 0.85。

## Session 数据

每个 `participant_id` / `session_id` 生成一条 session 记录。

字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `session_id` | string | session ID |
| `user_id` | string | 当前等于 `participant_id` |
| `participant_id` | string | 原始参与者 ID |
| `bfi_version` | string/null | 问卷版本 |
| `scene_count` | integer | 出现过的 `task_id` 数量 |
| `completed_scene_count` | integer | 至少一个回答非空的 scene 数量 |
| `event_count` | integer | event 总数 |
| `valid_event_count` | integer | `is_valid_event = true` 的 event 数量 |
| `low_quality_event_count` | integer | `is_low_quality = true` 的 event 数量 |
| `main_answer_count` | integer | 主回答 event 数 |
| `followup_answer_count` | integer | 追问回答 event 数 |
| `created_at_min` | string/null | session 内最早创建时间 |
| `created_at_max` | string/null | session 内最晚创建时间 |
| `is_effective_session` | boolean | 是否有效 session |
| `is_complete_session` | boolean | 是否完整 session |
| `quality_summary` | object/string | JSONL 中为对象，CSV 中为 JSON 字符串 |

有效 session：

```text
完成 BFI-2-S + 至少完成 5 个 scene + 至少 5 个 valid_event
```

完整 session：

```text
完成 BFI-2-S + 完成 6 个 scene + 至少 10 个 valid_event
```

脚本将“完成 BFI-2-S”定义为 `bfi_version == "BFI-2-S"` 且 `bfi_q1` 到 `bfi_q30` 全部非空。

## Quality Report

`v04_quality_report.json` 包含：

| 字段 | 说明 |
| --- | --- |
| `raw_row_count` | 原始 CSV 行数 |
| `event_count` | event 数 |
| `session_count` | session 数 |
| `label_count` | label 数 |
| `valid_event_count` | 有效 event 数 |
| `low_quality_event_count` | 低质量 event 数 |
| `effective_session_count` | 有效 session 数 |
| `complete_session_count` | 完整 session 数 |
| `scene_distribution` | 原始行按 `task_id` 分布 |
| `quality_flag_distribution` | 原始 `quality_flag` 分布 |
| `invalid_reasons_count` | event 质量问题分布，不含 `possible_prompt_copy` |
| `bfi_version_distribution` | label 的问卷版本分布 |
