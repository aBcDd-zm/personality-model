# 验证计划

第一版规则评分只是启发式 baseline，不是心理诊断。后续需要用心理测量和数据建模方法逐步验证。

## 1. 规则 baseline

先用现有 M6/M7 字段跑通最小闭环，确保每轮事件都能产出：

- `estimated_persona`
- M9 `feedback`
- evidence
- confidence

## 2. BFI 问卷对照

让同一批用户完成 BFI 或同类大五问卷，把问卷分数作为外部参照。

对照时使用 `metadata.user_id / session_id / timestamp` 进行样本匹配，但这些字段不进入 M1-M9 正式业务字段。

## 3. 小样本相关性

先收集 10-30 人小样本，计算：

- 规则分数与 BFI 五维的相关性。
- zero-shot LLM 分数与 BFI 五维的相关性。
- 不同事件类型下评分稳定性。

## 4. zero-shot LLM 对比

用同一批 M6/M7 数据让 zero-shot LLM 输出 JSON 评分，与规则 baseline 和 BFI 分数对比。

重点检查：

- 输出 JSON 稳定性。
- evidence 是否真实来自本轮行为。
- neuroticism 方向是否一致。
- 是否出现心理诊断或越界表述。

## 5. embedding + 回归模型

积累样本后，把用户文本转为 embedding，并训练回归模型预测 BFI 五维。

需要比较：

- 规则 baseline。
- zero-shot LLM。
- embedding + 回归模型。
- 心理语言学特征加回归模型。

## 6. 小模型微调

当样本量和标注质量足够后，再考虑小模型微调。微调前必须先明确：

- 训练标签来自何处。
- 信度和效度指标是否达标。
- 是否存在过拟合特定剧情或选项的风险。
- 前台是否会暴露评分逻辑并影响用户行为。

