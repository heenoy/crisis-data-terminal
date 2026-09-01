# 灾害事件死亡影响等级预测：Dummy 与 Random Forest 基线报告

## 1. 任务与防泄漏

- 输入：`data/processed_hdro/disaster_model_ready.csv`。
- 目标：预测灾害事件最终死亡影响等级 `impact_level`，顺序固定为 Low、Moderate、High、Extreme。
- 时间划分：训练 2000-2019；验证 2020-2021；测试 2022-2023；2024-2026 成熟度留置区完全未进入模型流程。
- 所有模型特征严格来自白名单：country_code, region, disaster_type, disaster_subtype, date_granularity, year, date_imputed, historical_frequency, hdi, hdi_missing, event_month, month_missing。
- `total_deaths`、影响人数、损失、结束日期、目标及标识符均被程序化泄漏检查阻止。
- 所有预处理器在训练期拟合；最终配置锁定后，仅在 2000-2021 重新拟合一次，再对测试集评估一次。

## 2. 验证集模型选择

- 共比较 2 个 Dummy、18 个 Random Forest 候选；RF-V1 与 RF-V2 各 9 个。
- 主要指标为验证集 macro-F1，差异在 0.002 内视为近似并列，再参考 Extreme Recall、High Recall 与模型复杂度。
- 最终选择：RF-V2_C09 / RF-V2。
- 最终参数：`{"class_weight": "balanced_subsample", "max_depth": 10, "max_features": 0.5, "min_samples_leaf": 5, "n_estimators": 500}`。
- 前两名验证 macro-F1 差 0.0200；仍需避免把单次时间窗口差异解释为普遍优势。

所选 RF 验证指标：
- accuracy: 0.6853
- balanced_accuracy: 0.5389
- macro_precision: 0.4845
- macro_recall: 0.5389
- macro_f1: 0.4825
- weighted_f1: 0.6903

## 3. 最终测试结果

- accuracy: 0.6487
- balanced_accuracy: 0.5890
- macro_precision: 0.5214
- macro_recall: 0.5890
- macro_f1: 0.5244
- weighted_f1: 0.6605

| 类别 | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Low | 0.6180 | 0.9016 | 0.7333 | 305 |
| Moderate | 0.9357 | 0.5553 | 0.6970 | 524 |
| High | 0.2388 | 0.3678 | 0.2896 | 87 |
| Extreme | 0.2931 | 0.5312 | 0.3778 | 32 |

测试集混淆矩阵（行是真实类别，列是预测类别，顺序 Low/Moderate/High/Extreme）：

| True | Low | Moderate | High | Extreme |
|---|---:|---:|---:|---:|
| Low | 275 | 11 | 15 | 4 |
| Moderate | 144 | 291 | 77 | 12 |
| High | 21 | 9 | 32 | 25 |
| Extreme | 5 | 0 | 10 | 17 |

## 4. 预处理与缺失

- 选择阶段训练期 HDI 中位数：0.655000，仅由 2000-2019 训练集拟合。
- 最终重拟合期 HDI 中位数：0.662000，仅由 2000-2021 开发集拟合。
- HDI 缺失指示变量保留；没有按未来或邻近年份填充。
- OneHotEncoder 使用 `handle_unknown="ignore"`。验证集与测试集未知类别统计见 `unknown_category_report.csv`。
- 月份仅在原始日期精度为月或日时提取；年精度事件的 `event_month` 保持缺失，并使用 `month_missing`。

## 5. 错误分析

- High 被预测为 Low/Moderate：30。
- Extreme -> Low：5；Extreme -> Moderate：0；Extreme -> High：10。
- HDI 缺失/非缺失、未知/已知类别、年份、灾害类型和地区差异见 `error_analysis.csv`。
- 测试结果仅用于最终评价和错误分析，没有返回修改参数。

## 6. 特征重要性

按原始字段聚合的前十项：
- disaster_type: 0.2525
- disaster_subtype: 0.2147
- hdi: 0.1667
- historical_frequency: 0.1040
- country_code: 0.0769
- region: 0.0608
- event_month: 0.0565
- year: 0.0559
- date_granularity: 0.0067
- date_imputed: 0.0028

- 展开后前 30 项见 `expanded_feature_importance.csv`；原字段聚合见 `aggregated_feature_importance.csv`。
- impurity importance 不是因果效应，高基数类别可能分散或放大重要性。
- permutation importance 仅在验证集计算，没有用测试重要性调参。

## 7. 可复现性与结论

- random_state=20260803；预测、指标、特征顺序、最终参数的可复现签名见 `reproducibility_signature.json`。
- 模型是否优于 most-frequent Dummy（验证 macro-F1）：是。
- 该结果适合作为论文中的 Random Forest 时间外推基线，但类别不平衡下 Extreme 样本仍少，不能过度解释一两个样本造成的召回变化。
- 本阶段没有运行 XGBoost、LightGBM、SMOTE 或深度学习。
