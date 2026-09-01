# 建模前字段审计与严格时间划分报告

## 1. 数据范围

- 正式输入：`data/processed_hdro/disaster_model_ready.csv`，13,582 行、26 列。
- 灾害年份：2000-2026。
- 本轮只做审计与切分建议，没有训练、拟合或保存任何模型。
- `impact_level` 仅由 `total_deaths` 生成：0-9 Low、10-99 Moderate、100-999 High、>=1000 Extreme；死亡人数缺失时标签为空，已在 model-ready 中排除。

## 2. 泄漏结论

- `total_deaths` 是直接目标来源，绝对禁止进入模型输入。当前没有 `casualties` 字段，也没有其他 death-related 派生特征。
- `total_affected`、`total_damage`、`end_date`、`duration` 与 `date_anomaly` 通常只能在事件发生后确认，若目标是在事件发生时预测影响等级，应排除。
- `hdi_match_status` 不是直接目标泄漏，但明显代理年份、地区和 HDI 可得性；不作为主要社会经济特征。模型只增加 `hdi_missing = hdi.isna()`。
- 推荐/条件推荐字段：country_code, region, disaster_type, disaster_subtype, year, event_date, date_granularity, date_imputed, historical_frequency, hdi。
- 排除或仅作目标/审计字段：event_id, country, total_deaths, total_affected, total_damage, event_date_upper, end_date, date_anomaly, duration, impact_level, time_batch, hdi_country_name, hdi_source, hdi_source_year, hdi_imputed, hdi_match_status。
- 完整逐字段结论见 `feature_audit.csv`。

## 3. HDI 缺失机制

| hdi_match_status | 数量 | 比例 |
|---|---:|---:|
| exact_year | 12,219 | 89.96% |
| missing_country_year | 169 | 1.24% |
| unsupported_country | 150 | 1.10% |
| after_hdi_range | 1,044 | 7.69% |

- Random Forest：在严格切分后，仅用训练集 HDI 中位数拟合填充器，并同时添加 `hdi_missing`；验证集和测试集只能调用该训练期参数。
- 原生支持 NaN 的模型：保留 NaN，并保留 `hdi_missing`。
- 禁止使用全数据中位数、未来年份、邻近年份或测试期统计量补齐。

## 4. 年度和灾害类型分布

- 年度表覆盖每年样本数、四类目标数量/比例、HDI 缺失率，以及全局数量最高的十类灾害：Flood, Road, Storm, Water, Epidemic, Mass movement (wet), Extreme temperature, Explosion (Industrial), Earthquake, Air。
- 详细数据见 `yearly_target_distribution.csv`。
- 2026 年只有 139 条，且 2024-2026 的伤亡和损失可能继续修订，不作为推荐测试集。

## 5. 严格时间划分候选

| scheme | subset | start_year | end_year | sample_count | low_count | moderate_count | high_count | extreme_count | hdi_missing_rate |
|---|---|---|---|---|---|---|---|---|---|
| A_conservative_backtest | train | 2000 | 2015 | 9041 | 2001 | 6282 | 683 | 75 | 2.83% |
| A_conservative_backtest | validation | 2016 | 2017 | 859 | 230 | 568 | 59 | 2 | 3.03% |
| A_conservative_backtest | test | 2018 | 2020 | 1275 | 394 | 792 | 80 | 9 | 1.73% |
| B_recommended_stable_recent | train | 2000 | 2019 | 10786 | 2464 | 7439 | 801 | 82 | 2.74% |
| B_recommended_stable_recent | validation | 2020 | 2021 | 804 | 322 | 433 | 42 | 7 | 1.62% |
| B_recommended_stable_recent | test | 2022 | 2023 | 948 | 305 | 524 | 87 | 32 | 1.05% |
| C_rolling_origin_sensitivity | train | 2000 | 2017 | 9900 | 2231 | 6850 | 742 | 77 | 2.85% |
| C_rolling_origin_sensitivity | validation | 2018 | 2019 | 886 | 233 | 589 | 59 | 5 | 1.58% |
| C_rolling_origin_sensitivity | test | 2020 | 2022 | 1275 | 473 | 693 | 88 | 21 | 1.49% |

成熟度留置区：

| scheme | start_year | end_year | sample_count | hdi_missing_rate |
|---|---|---|---|---|
| A_conservative_backtest | 2021 | 2026 | 2407 | 44.00% |
| B_recommended_stable_recent | 2024 | 2026 | 1044 | 100.00% |
| C_rolling_origin_sensitivity | 2023 | 2026 | 1521 | 68.90% |

### 建议

推荐 `B_recommended_stable_recent`：2000-2019 训练、2020-2021 验证、2022-2023 测试，2024-2026 留置。它在保持严格时间顺序的同时，使用相对近期且更可能稳定的测试年份。

所有编码器、稀有类别规则、HDI 中位数、缺失处理器及任何特征选择都只能在训练集拟合。验证集用于调参，测试集在最终选择确定前保持封存。`historical_frequency` 直接使用现有因果实现，不重新累计或随机重排。

## 6. 训练前仍需确认

1. 明确预测时点为事件发生时；若预测时点不同，重新审查事后字段可用性。
2. 确认采用推荐时间切分，并将 2024-2026 保持为成熟度留置区。
3. 确认主基线特征清单及高基数国家/灾害亚型的编码策略。
4. 在训练流水线中用断言阻止 `total_deaths`、目标列和事后字段进入 X。
