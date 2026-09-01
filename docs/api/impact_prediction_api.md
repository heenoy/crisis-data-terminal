# 影响等级辅助分析 API

本接口仅加载已经冻结的三级 Random Forest T2 Pipeline，用于灾害档案辅助分析。接口不会重新训练、重新拟合或在线更新模型，也不接收死亡人数、受影响人数、经济损失等事后字段。

## 接口

### `GET /api/health`

返回服务可用状态、模型名称与固定类别顺序，不返回服务器路径或内部哈希。

### `GET /api/impact-options`

返回冻结的国家、灾害类型—子类型、日期精度和 Magnitude 量表选项，供表单使用。

### `POST /api/predict-impact`

请求体上限为 8192 字节，仅接受以下白名单字段：

```json
{
  "country_code": "CHN",
  "disaster_type": "Flood",
  "disaster_subtype": "Flood (General)",
  "event_date": "2023-07-15",
  "date_granularity": "day",
  "magnitude": 1000,
  "magnitude_scale": "Km2"
}
```

`magnitude` 与 `magnitude_scale` 可同时省略。日期格式随精度分别为 `YYYY-MM-DD`、`YYYY-MM`、`YYYY`。接口拒绝白名单外字段，因此 `total_deaths`、`total_affected`、`total_damage` 等不能混入预测请求。

成功响应包含预测等级、三类模型输出概率、输入质量提示、模型参考信息和固定免责声明。输出概率未经校准，只表示冻结模型的相对输出强度；三类概率之和在 `1e-12` 误差内等于 1。

## 稳定错误码

包括 `EMPTY_REQUEST`、`INVALID_JSON`、`REQUEST_TOO_LARGE`、`UNKNOWN_FIELDS`、`MISSING_FIELD`、`UNKNOWN_COUNTRY_CODE`、`UNKNOWN_DISASTER_TYPE`、`UNKNOWN_DISASTER_SUBTYPE`、`INVALID_TYPE_SUBTYPE_PAIR`、`INVALID_DATE_GRANULARITY`、`INVALID_EVENT_DATE`、`INVALID_MAGNITUDE` 和 `MISSING_MAGNITUDE_SCALE`。响应不包含 Python 堆栈、模型路径或内部异常详情。

## 安全边界

接口同源使用，不设置任意来源 CORS；不保存请求和预测；服务端日志处理器不记录请求内容。模型仅在 Python 服务端加载，前端产物不包含模型文件。
