# 第三阶段 Severe 开发候选锁定记录

锁定时间：2026-08-31T07:20:34.133447+00:00。仅Development配方锁定，不是Production模型冻结。

推荐：**RF_T2**。Test评价尚未授权；Maturity继续封存。

| candidate_id | accuracy | balanced_accuracy | macro_f1 | weighted_f1 | severe_precision | severe_recall | severe_f1 | severe_to_low | severe_to_low_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LGBM_T2 | 0.6757 | 0.6097 | 0.5654 | 0.6891 | 0.2157 | 0.3577 | 0.2691 | 68 | 0.2764 |
| RF_T2 | 0.6763 | 0.6385 | 0.5794 | 0.6891 | 0.2459 | 0.4268 | 0.3120 | 61 | 0.2480 |

阈值：
- RF_T2: 没有满足 Precision≥0.45 的阈值；不放宽底线。
- LGBM_T2: 没有满足 Precision≥0.45 的阈值；不放宽底线。

权重：没有权重候选同时达到 Precision≥0.45 且 Severe F1 严格优于原基准，因此不保留优化权重及其组合；不降低底线、不搜索额外倍率。

固定种子20260803。配置SHA-256：`80df528b9ef7e79a5f6c5ae61de1ee23f80d802f525e696381e1fd860fc356f9`。
训练脚本SHA-256：`59d6cd8606bd46b4b280330c4c7c63d13bb1a6b815bc68eb2aac5f94a2a7ec11`。
完整参数、选择规则、实际权重、预处理统计、代码版本和OOF见独立实验目录及 `development_candidate_lock.json`。

阈值/权重由相同OOF选择与展示，不作为独立Test结果。未经批准不读取Test评价新候选；不改变原冻结RF-T2，不恢复第四阶段。
