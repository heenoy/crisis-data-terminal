# EM-DAT 与 HDI 数据融合分析报告

## 1. 输入文件与原始规模

- EM-DAT: `emdat_raw.xlsx` / `EM-DAT Data`，16,858 行、47 列。
- HDI: `HDR25_Statistical_Annex_HDI_Trends_Table.xlsx` / `Table 2. HDI trends`，宽表转长表后 1,584 个有效国家-年份值。
- HDI 可用年份：1990, 2000, 2010, 2015, 2020, 2021, 2022, 2023。
- 输入文件均只读，输出写入独立目录；没有覆盖原始文件。

## 2. 实际字段映射

| 标准字段 | 原始字段 |
|---|---|
| event_id | DisNo. |
| country | Country |
| country_code | ISO |
| region | Subregion |
| disaster_type | Disaster Type |
| disaster_subtype | Disaster Subtype |
| start_year | Start Year |
| start_month | Start Month |
| start_day | Start Day |
| end_year | End Year |
| end_month | End Month |
| end_day | End Day |
| total_deaths | Total Deaths |
| total_affected | Total Affected |
| total_damage | Total Damage ('000 US$) |

## 3. 日期构造与 duration

- 完整年月日直接使用；开始日缺日时取当月 1 日，缺月和日时取当年 1 月 1 日。
- 结束日缺日时取当月最后一天，缺月和日时取当年 12 月 31 日。
- `duration` 单位为天，按 `end_date - event_date + 1` 计算；结束日期缺失或早于开始日期时保持为空。
- 开始日期不完整 1,592 条；开始年份缺失/日期无效 0 条；结束日期缺失 0 条；结束日期不完整 1,507 条；结束早于开始 1 条。

## 4. 国家标准化与 HDI 合并

- 优先保留 EM-DAT 的 ISO3 代码；由于本 HDI 表没有 ISO3，实际连接键为集中别名映射后的标准化国家名 + 灾害开始年份。
- HDI 仅执行同国同年精确匹配，不插值、不前向填充、不使用最近年份。
- HDI 精确匹配 4,354/16,858 条，匹配率 25.83%；缺失 12,504 条，缺失率 74.17%。
- 缺失原因：国家未匹配/HDI 不含该国 286；HDI 有该国但缺该年份 10,937；灾害年份超出 HDI 总年份范围 1,281；灾害年份缺失 0。
- HDI 重复国家-年份输入行 0 条（无冲突时去重），合并没有导致行数膨胀。

主要未匹配国家（按记录数）：
- Taiwan (Province of China): 92 条
- Democratic People's Republic of Korea: 42 条
- Puerto Rico: 29 条
- Canary Islands: 16 条
- Serbia Montenegro: 16 条
- Réunion: 10 条
- Cayman Islands: 7 条
- Turks and Caicos Islands: 7 条
- Guam: 6 条
- Northern Mariana Islands: 6 条
- Guadeloupe: 6 条
- Martinique: 5 条
- China, Macao Special Administrative Region: 4 条
- Mayotte: 4 条
- American Samoa: 4 条
- Cook Islands: 4 条
- New Caledonia: 3 条
- United States Virgin Islands: 3 条
- Bermuda: 3 条
- French Polynesia: 3 条
- British Virgin Islands: 2 条
- French Guiana: 2 条
- Tokelau: 1 条
- Netherlands Antilles: 1 条
- Saint Helena: 1 条
- Niue: 1 条
- Anguilla: 1 条
- Sint Maarten (Dutch part): 1 条
- Saint Barthélemy: 1 条
- Azores Islands: 1 条

## 5. total_deaths 与 impact_level

- `total_deaths` 先去除千位分隔符再数值化；无法解析、缺失或负值均不分配标签。缺失/非数值 3,276 条，负值 0 条。
- 边界固定为：0–9 Low、10–99 Moderate、100–999 High、≥1000 Extreme；缺失不当作 0。

| impact_level | 数量 | 占有效标签比例 |
|---|---:|---:|
| Low | 3393 | 24.98% |
| Moderate | 9029 | 66.48% |
| High | 1017 | 7.49% |
| Extreme | 143 | 1.05% |

## 6. historical_frequency 与无泄漏规则

- 含义是当前事件之前同国已经发生的事件数。按国家、可用时间粒度排序并以批次累计，不使用全量国家总数回填。
- 完整日期按“同国同日”为批次；某国某月只要存在缺日记录，该月全部事件按月批次；某国某年只要存在缺月记录，该年全部事件按年批次。同批事件共享批次开始前的累计次数，整批结束后才增加计数，避免补全日期或原始行顺序制造虚假先后关系。
- 自动验证：
- earliest_is_zero: 通过
- non_decreasing: 通过
- same_batch_equal: 通过
- 抽样明细见 `historical_frequency_validation.csv`。

## 7. 完整性与质量结论

- 合并前后均为 16,858 行，行数一致：是。
- 重复 `event_id` 记录 0 条；未静默删除，需在建模前核实。
- 有效标签建模集 13,582 行；主合并集保留所有记录。
- 当前是否建议进入 Random Forest 训练：有条件建议。本次未训练任何模型。

## 8. 建模前仍需处理的问题

1. HDI 年份极稀疏，仅精确年份可匹配；若要扩大覆盖率，应先确定有依据的插值策略并单独评估，不能直接最近年份填充。
2. 核实缺失/非数值 `total_deaths` 与重复事件标识，明确标签可用范围及去重规则。
3. 检查部分日期事件的批次粒度和结束早于开始的源数据异常，再制定训练/测试的时间切分方案。
