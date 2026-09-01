# Frozen T2 inference

本目录封装冻结三级 Random Forest T2 模型。`feature_builder.py` 只读取 `frozen_assets/`，构造固定 15 项特征；`loader.py` 在模块初始化时校验模型 SHA-256 并加载；`response_builder.py` 生成稳定 API 合同。

使用 Python 3.12 与根目录 `requirements.txt` 的固定版本运行：

```powershell
python -m unittest ml_inference.tests.test_api_contract ml_inference.tests.test_http_api -v
python ml_inference/tests/verify_test_consistency.py
python ml_inference/tests/measure_runtime.py
```

重新生成辅助快照时使用 `ml_inference/scripts/build_frozen_assets.py`。该脚本不训练或重新序列化模型，只复制并校验冻结模型、从冻结数据导出只读查找表。
