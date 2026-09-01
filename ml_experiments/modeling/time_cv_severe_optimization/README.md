# Development 时间 CV、OOF 阈值与类别权重实验

仅使用 2000–2021 年 Development。既有 Frozen RF-T2、Test 预测和系统代码不修改。

## 运行前审计

- 同一四折扩展窗口：2000–2013→2014–2015、2000–2015→2016–2017、2000–2017→2018–2019、2000–2019→2020–2021。
- 验证集 Severe 分别为 72、61、64、49；合计 OOF 3466 条，仅覆盖 2014–2021，不称为全部 Development 的 OOF。
- 冻结源文件哈希已与 final_t2 manifest 核对。
- `historical_frequency` 为同国日期可用区间上界严格小于当前下界的先前事件数；包含无标签历史事件。独立重算与原字段零差异，各折前缀截断结果一致。验证窗口内先发生且日期区间已结束的事件可作为后续事件历史，模拟顺序到达，不是窗口起点一次性静态预测。
- 事件 ID 的年份前缀不总等于发生年份，因此使用正式 `year` 列筛选，不能以 ID 前缀决定时间折。
- 共享 CSV/XLSX 容器需要流式扫描及读取用于排除的年份/ID；Test/Maturity 的特征、标签均不进入实验数据帧或计算。不能声称物理上没有扫描过包含它们的文件字节。后续训练只读取独立的 Development 缓存。
- 原始 Magnitude 只在构造步骤使用；八个语义组定义不变，每折训练部分拟合 n、median、IQR，n<20/IQR=0 不生成 z，裁剪 [-5,5]。
- RF 使用冻结 T2 的 15 特征顺序、OneHot 与中位数填补。LightGBM 使用同样 15 特征但原生类别和 NaN；词表仅在该折训练数据拟合。
- 历史 `LGBM-V2_P3_low_rate_balanced` 确认为 291 轮；本轮所有折固定 291 轮，不 early stopping、不逐折选参，仅把目标改为原生三级、输入改为共同 T2 15 特征。
- 历史 LightGBM 配置曾利用 2020–2021 Validation 选出；因此本轮是复用历史配置的 Development 比较，不是完全嵌套、无选择偏差的外层 CV。也不重新用其历史 Test 指标选型。

## 预先固定的决策规则

`config.json` 在模型训练前写入。固定种子 20260803；阈值 0.20–0.60，步长 0.01；权重倍率 1.25/1.5/2/2.5，加固定 balanced×1.0 方法对照。

只在 OOF Severe Precision≥0.45 时按 Recall、F1、Macro F1、Severe→Low 比例排序；阈值并列时用相对默认 argmax 的预测变更数较少者，最后按 ID 稳定破同分。0.45 是本实验预设误报约束，不是专业业务风险标准；若无可行项，禁止降低底线。

组合只把基准 RF 选出的一个阈值原样用于一个选定权重，禁止二维搜索。OOF 同时用于阈值/权重选择与展示，因此优化候选的 OOF 指标存在选择乐观偏差，不能充当独立 Test 结论。

## 权重语义

本机 scikit-learn 1.9.0 `_parallel_build_trees` 源码确认：`balanced_subsample` 在每棵树抽样后计算类别平衡权重；固定字典在训练折按 `N/(3*n_c)` 计算后，Severe 乘倍率。1.9.0 会把传入的 sample/class weights 用于 bootstrap 抽样概率，随后通过重复计数拟合树。两者并非同一机制，所以保留固定字典×1.0 对照；不把固定字典方案称为逐树动态 balanced_subsample 的精确倍率版本。

## 环境

使用项目 `.venv` 的 Python；历史 sklearn/numpy/pandas/joblib 精确版本不更改。缺少的 LightGBM 4.6.0 及绘图依赖安装到本目录被忽略的 `.dependencies`，不修改推理 requirements 或系统环境。实验脚本运行期间不联网。

审计命令：

```powershell
.venv\Scripts\python.exe ml_experiments/modeling/time_cv_severe_optimization/time_cv_oof_threshold_class_weight.py --audit --output ml_experiments/modeling/time_cv_severe_optimization/audit
```

审计 CSV 列出逐年及逐折真实类别数量。第四阶段继续暂停。

完整实验与复现命令（输出目录必须不存在，防止覆盖）：

```powershell
.venv\Scripts\python.exe ml_experiments/modeling/time_cv_severe_optimization/time_cv_oof_threshold_class_weight.py --output ml_experiments/modeling/time_cv_severe_optimization/run1
.venv\Scripts\python.exe ml_experiments/modeling/time_cv_severe_optimization/time_cv_oof_threshold_class_weight.py --output ml_experiments/modeling/time_cv_severe_optimization/run2
.venv\Scripts\python.exe ml_experiments/modeling/time_cv_severe_optimization/finalize_time_cv_report.py
.venv\Scripts\python.exe -m unittest discover -s ml_experiments/modeling/time_cv_severe_optimization -p test_time_cv.py
```

已有结果后重新实验请使用独立输出名称，保留run1/run2作为已验收运行记录，不覆盖冻结报告。所有中间权重均为实验记录，不保存为正式模型版本；最终锁定的是配方而非生产模型。本轮不在完整Development上拟合替换模型。

优化权重的保留额外要求Severe F1严格优于RF-T2基准，否则即使个别召回率上涨也不保留组合。环境安装版本记录在运行元数据；独立绘图依赖为LightGBM 4.6.0、Matplotlib 3.11.1、contourpy 1.3.3、cycler 0.12.1、fonttools 4.63.0、kiwisolver 1.5.1、packaging 26.3、Pillow 12.3.0、pyparsing 3.3.2。Python主环境为本机项目3.14.2，与历史3.12.13不同；sklearn/numpy/pandas/joblib精确版本保持一致，本轮通过独立重复训练验证结果。
