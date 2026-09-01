# 可审计基线训练

正式输入固定为 `data/processed_hdro/disaster_model_ready.csv`。任务是“灾害事件死亡影响等级预测”。

运行：

```powershell
ml_experiments/disaster_impact_prediction/.venv/Scripts/python.exe ml_experiments/modeling/train_baseline.py
```

流水线严格采用方案 B：2000-2019 训练、2020-2021 验证、2022-2023 测试；2024-2026 只验证归属，不进入任何预处理、训练或评价。

所有模型输入必须来自 `feature_config.py` 白名单。`total_deaths`、目标、影响/损失、结束日期及标识符被泄漏断言拒绝。候选模型只用验证集选择，最终配置锁定后在 2000-2021 重新拟合，并对测试集评价一次。
