# 热带气旋外部强度数据接入可行性审计

EXPLORATORY  
NOT FOR MODEL SELECTION  
NOT DEPLOYED

独立数据可行性审计，非第三阶段正式主线。只使用 Development 2000–2021；不读取 Test 预测/标签，不提取 Maturity。包含无死亡标签的热带气旋，匹配逻辑不读取用于范围描述的 Severe 标记。

## 当前归档状态

**LIMITED_FEASIBILITY / INCOMPLETE_NETWORK_BLOCKED**。官方HEAD返回200，但实际CSV传输中断。残留文件只有2,942字节的表头和单位行、没有轨迹行，已标记 `INCOMPLETE`，禁止用于匹配。

已完成范围及文档时点审计；匹配数、唯一匹配率、合格强度覆盖率均为 `null / measured=false`，不是0%。`match`为未执行、未验证的规则草案，不能视为已验证匹配流程。此次按用户网络停止条件归档；不要自动重试、换镜像或推进特征。若以后获准恢复，需要重新完成官方数据获取与匹配实现验证。

## 已实施流程与复核

使用现有项目环境，不安装依赖：

```powershell
.venv/Scripts/python.exe ml_experiments/exploratory/tropical_cyclone_audit/audit_ibtracs_feasibility.py scope
$env:PYTHONPATH='D:/crisis-data-terminal/ml_experiments/modeling/time_cv_severe_optimization/.dependencies'
.venv/Scripts/python.exe ml_experiments/exploratory/tropical_cyclone_audit/audit_ibtracs_feasibility.py verify
```

`download` 仅访问 NOAA/NCEI 官方来源，无网络重试或镜像回退。共享官方响应只将 ISO_TIME 落在2000–2021的原始行写入本目录；文件是保留原始头、单位及行字节的时间子集，不是完整官方CSV。下载清单分别记录官方源大小、子集大小和子集SHA-256。

如目录已有原始文件，不重新下载或覆盖。处理结果默认只允许新增或确认已有字节相同，`verify`不修改已有CSV/JSON。外部源可能更新，本地原始子集及清单构成此次审计的固定输入。

## 规则与解释

- 范围：`Storm / Tropical cyclone`；不把 Storm (General)、温带风暴或龙卷风自动当热带气旋。
- 规则在首次匹配前保存于 `checksums/matching_rules_locked.json`：起始日期区间±3天、精确名称token、海域一致性；不用结束日期、死亡、预测或性能调整规则。
- 现有EM-DAT名称中的台风/飓风/cyclone等描述词被去除，但不做模糊匹配或自动别名猜测。
- 仅海域相容不证明轨迹影响具体国家，更不证明Location精确可靠。本轮未加入未经核验的地图或地理编码，因此无充分空间证据的唯一候选最多为MEDIUM。
- 多个合理SID必须保留AMBIGUOUS，不自动选最近/最强候选。单个SID但缺少足够姓名/日期依据仍为UNMATCHED，候选证据保留。
- `provisional_sid`不是正式接受的连接，`accepted_sid`只允许HIGH；不要将MEDIUM候选自动导入特征表。
- `provisional_window_field_presence.csv`仅表示候选时间窗内曾有字段值；不是已选中的登陆强度、不是事前特征。
- IBTrACS `ISO_TIME`是轨迹时刻，不是发布时刻；`MAIN`包含再分析，`LANDFALL`涉及下一轨迹时刻。未经历史发布版本核验不得认定为事前可用。

## 产物

- `data/raw/`：官方时段原始行及官方文档。
- `data/processed/`：独立候选字段有值情况；禁止接入正式模型。
- `reports/`：范围表、候选证据、每事件匹配结论、字段和可行性统计。
- `checksums/`：白名单、规则、原始来源、输出及受保护文件验证。
- 完整中文报告：`docs/exploratory/热带气旋外部强度数据接入可行性审计.md`。

不修改15项特征、冻结模型/Manifest、正式Test报告、project-status或业务代码；不训练模型、不计算新模型效果。本轮停止条件触发后只归档审计，不继续开发特征。
