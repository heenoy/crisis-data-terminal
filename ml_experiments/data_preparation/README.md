# HDRO HDI 数据采集与 EM-DAT 融合

本目录只处理 HDRO Data API 元数据/年度 HDI 采集、EM-DAT 融合、特征构造和质量验证，不训练模型。

## 1. 环境

在项目根目录 `.env` 或进程环境中配置 `HDRO_API_KEY`。脚本不会打印或保存密钥。

## 2. 采集

```powershell
python ml_experiments/data_preparation/fetch_hdro_hdi.py --stage coverage
python ml_experiments/data_preparation/fetch_hdro_hdi.py --stage bulk --batch-size 20
```

批量过程先写 `data/raw/hdro_hdi_response.batch.json` 与 `hdro_hdi_annual.staging.csv`。验证国家年份唯一性、范围、AFG 回归和响应结构后才更新正式年度文件。脚本可重跑，并从暂存清单跳过已完成代码。

## 3. 融合

```powershell
python ml_experiments/data_preparation/prepare_disaster_data.py
```

新版结果只写入 `data/processed_hdro/`。HDI 严格按 ISO3 + 灾害年份精确合并，不插值、不外推；旧版 `data/processed/` 不会被覆盖。

`historical_frequency` 使用日期精度对应的真实时间区间，仅累计明确结束于当前批次之前的事件，避免不完整日期造成未来信息泄漏。

