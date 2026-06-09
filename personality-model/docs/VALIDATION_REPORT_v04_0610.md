# VALIDATION_REPORT_v04_0610

## 1. 验证目标

本轮使用 0609_personality_dataset_20260610_050318.csv 作为最新原始数据，对 personality-model v0.4 生成的 session_score 与 BFI-2-S 问卷标签进行小样本对照验证。

## 2. 对比字段

| 维度 | 模型字段 | BFI 标签字段 |
|---|---|---|
| O | `personality_openness` | `bfi_O_100` |
| C | `personality_conscientiousness` | `bfi_C_100` |
| E | `personality_extraversion` | `bfi_E_100` |
| A | `personality_agreeableness` | `bfi_A_100` |
| N | `personality_neuroticism` | `bfi_N_100` |

## 3. 样本过滤

- all：所有能按 session_id 对齐的 session。
- clean：保留 aggregated_event_count >= 10、skipped_event_count <= 2，且 BFI 标签不是全 50 的 session。

## 4. 汇总结果

| group | trait | n | MAE | mean error | Pearson | Spearman |
|---|---|---:|---:|---:|---:|---:|
| all | O | 43 | 14.8869 | -1.7298 | -0.0271 | -0.1484 |
| all | C | 43 | 34.7845 | 34.739 | 0.1235 | 0.0913 |
| all | E | 43 | 34.7839 | -34.4745 | 0.2205 | 0.236 |
| all | A | 43 | 20.1203 | 19.432 | 0.0373 | 0.0704 |
| all | N | 43 | 30.4322 | -27.7508 | 0.2801 | 0.33 |
| clean | O | 35 | 14.8048 | -1.3687 | -0.2906 | -0.3613 |
| clean | C | 35 | 34.582 | 34.5261 | 0.0724 | -0.0059 |
| clean | E | 35 | 38.0198 | -37.6397 | 0.2049 | 0.1553 |
| clean | A | 35 | 20.8973 | 20.0517 | -0.0179 | 0.0522 |
| clean | N | 35 | 30.6549 | -27.6463 | 0.3007 | 0.3725 |

## 5. 当前说明

当前仍属于小样本流程验证，样本量和数据质量有限，因此 MAE、Pearson、Spearman 只能作为初步信号，不能作为模型有效性的正式结论。

## 6. 下一步

1. 检查 MAE 较高的维度，判断 rule scoring 是否系统性偏高或偏低。
2. 排除乱填文本、全 3 问卷和事件数不足的 session。
3. 根据误差方向调整 rule / hybrid 权重。
4. 后续再接入 DeepSeek / LLM 或 embedding regression。