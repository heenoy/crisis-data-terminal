# 原始输入与冻结 T2 特征映射

| 冻结特征 | 来源 | 构造规则 |
|---|---|---|
| country_code | 请求直接提供 | 转大写后核对冻结 ISO3 映射 |
| region | 后端构造 | 冻结国家—地区表精确查找 |
| disaster_type | 请求直接提供 | 必须属于冻结支持列表 |
| disaster_subtype | 请求直接提供 | 必须与灾害类型构成冻结有效组合 |
| date_granularity | 请求直接提供 | day、month、year 三选一 |
| year | 后端构造 | 从与精度一致的 event_date 解析 |
| date_imputed | 后端构造 | 月或年精度为 1，日精度为 0；不伪造月日 |
| historical_frequency | 后端构造 | 同国冻结档案中，时间区间结束严格早于当前事件区间开始的事件数 |
| hdi | 后端构造 | 冻结 HDI 表按 ISO3 与事件年份精确查找 |
| hdi_missing | 后端构造 | 精确年度 HDI 缺失时为 1 |
| event_month | 后端构造 | 日/月精度取真实月份；年精度保持缺失 |
| month_missing | 后端构造 | 仅年精度为 1 |
| magnitude_robust_z | 后端构造 | 合格语义组使用 Development 中位数和 IQR，裁剪到 [-5,5] |
| magnitude_missing | 后端构造 | Magnitude 未提供时为 1 |
| magnitude_group_unknown | 后端构造 | 缺少合格冻结语义组时为 1 |

所有 15 项特征按上述固定顺序送入原 Pipeline。Pipeline 内部只执行冻结的缺失填补、One-Hot 编码和 Random Forest 推断；API 不调用任何 `fit` 方法。

Magnitude 支持组为 `Earthquake | Moment Magnitude`、`Flood | Km2`、`Storm | Kph`、`Wildfire | Km2`、`Cold wave | °C`、`Heat wave | °C` 与 `Severe winter conditions | °C`。`Drought | Km2` 在 Development 中仅 1 个有效样本且 IQR 为 0，因此不生成 z 值并标记未知组。组内 z 值只表示同语义组相对位置，不能跨灾害类型或量表比较。
