"""Compare two completed CV runs, plot real OOF data, and lock development recipes."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import time_cv_oof_threshold_class_weight as exp
import numpy as np
import pandas as pd

sys.path.insert(0, str(exp.HERE / ".dependencies"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE, ROOT = exp.HERE, exp.ROOT
REP = HERE.parent / "reports"
FIG = REP / "figures/third_stage_severe"
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]


def md_table(df, digits=4):
    def fmt(v):
        if isinstance(v, (float, np.floating)): return f"{v:.{digits}f}"
        return str(v)
    return "\n".join(["| " + " | ".join(df.columns) + " |", "| " + " | ".join(["---"] * len(df.columns)) + " |"] +
                     ["| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False, name=None)])


def savefig(name, fig):
    fig.tight_layout()
    fig.savefig(FIG / (name + ".png"), dpi=180, facecolor="white")
    plt.close(fig)


def line_fold(folds, metric, name):
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for i, mid in enumerate(["RF_T2", "LGBM_T2"]):
        f = folds[folds.model_id.eq(mid)]
        ax.plot(f.fold, f[metric], marker="o", color=COLORS[i], label=mid)
    ax.set(ylim=(0, 1), xticks=[1, 2, 3, 4], xlabel="Temporal fold", ylabel=metric.replace("_", " ").title(),
           title="Development temporal CV OOF — " + metric.replace("_", " ").title())
    ax.grid(alpha=.2); ax.legend()
    savefig(name, fig)


def confusion(cm, title, name):
    fig, ax = plt.subplots(figsize=(6.2, 5))
    ax.imshow(cm, cmap="Blues", vmin=0)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, str(cm[i][j]), ha="center", va="center", fontsize=13,
                    color="white" if cm[i][j] > np.max(cm) * .5 else "black")
    ax.set(xticks=range(3), yticks=range(3), xticklabels=exp.LABELS, yticklabels=exp.LABELS,
           xlabel="Predicted class", ylabel="True class", title=title + "\nDevelopment temporal CV OOF")
    savefig(name, fig)


def main():
    a, b = HERE / "run1", HERE / "run2"
    cfg = json.loads(exp.CFG_PATH.read_text(encoding="utf-8"))
    r1 = json.loads((a / "time_cv_severe_optimization.json").read_text(encoding="utf-8"))
    r2 = json.loads((b / "time_cv_severe_optimization.json").read_text(encoding="utf-8"))
    audit = json.loads((HERE / "audit/audit.json").read_text(encoding="utf-8"))
    assert r1 == r2, "CV summaries differ between runs"
    assert r1["config_sha256"] == exp.sha(exp.CFG_PATH)
    assert r1["script_sha256"] == exp.sha(HERE / "time_cv_oof_threshold_class_weight.py")
    pa, pb = [pd.read_csv(folder / "time_cv_oof_predictions.csv", float_precision="round_trip") for folder in (a, b)]
    keys = ["event_id", "year", "true_label", "predicted_label", "fold", "model_id"]
    assert pa[keys].equals(pb[keys])
    historical = pd.read_csv(HERE.parent / "three_class/predictions/validation_predictions_T2.csv").set_index("event_id")
    fold4 = pa[(pa.model_id == "RF_T2") & (pa.fold == 4)].set_index("event_id")
    assert set(fold4.index) == set(historical.index)
    assert fold4.predicted_label.equals(historical.loc[fold4.index, "predicted_label"])
    historical_prob_error = float(np.max(abs(fold4[[f"probability_{c}" for c in exp.LABELS]].to_numpy() -
        historical.loc[fold4.index, [f"probability_{c.lower()}" for c in exp.LABELS]].to_numpy())))
    assert historical_prob_error <= 1e-12
    probability_cols = [f"probability_{c}" for c in exp.LABELS]
    max_error = float(np.max(abs(pa[probability_cols].to_numpy() - pb[probability_cols].to_numpy())))
    assert max_error <= cfg["reproducibility"]["probability_atol"]
    assert (a / "fold_preprocessing.json").read_bytes() == (b / "fold_preprocessing.json").read_bytes()
    for f in range(1, 5): assert (a / f"magnitude_fold{f}.csv").read_bytes() == (b / f"magnitude_fold{f}.csv").read_bytes()
    before = json.loads((a / "protected_hashes_before.json").read_text(encoding="utf-8"))
    assert exp.snapshot() == before
    comparisons = ["fold_metrics.csv", "candidate_comparison.csv", "severe_threshold_search.csv", "severe_weight_search.csv"]
    for filename in comparisons:
        aa, bb = [pd.read_csv(folder / filename) for folder in (a, b)]
        pd.testing.assert_frame_equal(aa, bb, atol=1e-15, rtol=0)
    reproducibility = {"full_cv_runs": 2, "classes_identical": True, "max_probability_absolute_error": max_error,
        "probability_tolerance": 1e-12, "metric_tolerance": 1e-15, "metrics_identical": True,
        "category_vocabularies_identical": True, "magnitude_statistics_identical": True,
        "configuration_identical": True, "model_sha256": exp.sha(exp.FROZEN),
        "fold4_historical_validation_classes_identical": True,
        "fold4_historical_probability_max_error": historical_prob_error,
        "protected_files_unchanged": len(before)}
    exp.dump(HERE / "reproducibility.json", reproducibility)
    FIG.mkdir(parents=True, exist_ok=False)
    tables = {name: pd.read_csv(a / name) for name in ["fold_metrics.csv", "candidate_comparison.csv",
                "severe_threshold_search.csv", "severe_weight_search.csv", "fold_metric_summary.csv", "pooled_oof_metrics.csv"]}
    for name, df in tables.items(): df.to_csv(FIG / name, index=False)
    folds = tables["fold_metrics.csv"]
    line_fold(folds, "severe_recall", "01_severe_recall_by_fold")
    line_fold(folds, "severe_f1", "02_severe_f1_by_fold")
    ts = tables["severe_threshold_search.csv"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, mid in zip(axes, ["RF_T2", "LGBM_T2"]):
        data = ts[(ts.model_id == mid) & (ts.fold == "pooled")]
        for i, metric in enumerate(["severe_precision", "severe_recall", "severe_f1"]):
            ax.plot(data.threshold, data[metric], color=COLORS[i], label=metric.replace("severe_", ""))
        ax.axhline(.45, color="gray", ls="--", lw=1, label="Precision floor (0.45)")
        ax.set(ylim=(0, 1), xlabel="Severe threshold", ylabel="Score", title=mid)
        ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle("Development temporal CV OOF — threshold search")
    savefig("03_severe_threshold_curve", fig)
    weights = tables["severe_weight_search.csv"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for i, metric in enumerate(["severe_precision", "severe_recall", "severe_f1", "severe_to_low_rate"]):
        ax.plot(weights.multiplier, weights[metric], marker="o", color=COLORS[i], label=metric)
    ax.set(ylim=(0, 1), xticks=weights.multiplier, xlabel="Severe multiplier on fold-balanced dictionary",
           ylabel="Score / rate", title="Development temporal CV OOF — RF class weights")
    ax.grid(alpha=.2); ax.legend(fontsize=8)
    savefig("04_class_weight_curve", fig)
    candidates = tables["candidate_comparison.csv"]
    fig, ax = plt.subplots(figsize=(12, 5))
    metric_names = ["macro_f1", "balanced_accuracy", "severe_precision", "severe_recall", "severe_f1"]
    x = np.arange(len(candidates)); width = .15
    for i, metric in enumerate(metric_names):
        ax.bar(x + (i - 2) * width, candidates[metric], width, color=COLORS[i], label=metric)
    ax.set(ylim=(0, 1), xticks=x, xticklabels=candidates.candidate_id, ylabel="Score",
           title="Development temporal CV OOF — locked candidate recipes")
    ax.tick_params(axis="x", labelrotation=15); ax.legend(fontsize=8, ncol=3)
    ax.grid(axis="y", alpha=.2)
    savefig("05_candidate_comparison", fig)
    confusion(r1["baseline_confusion_matrix"], "RF-T2 default", "06_rf_t2_oof_confusion")
    confusion(r1["selected_confusion_matrix"], r1["recommended_development_candidate"], "07_selected_oof_confusion")
    exp.dump(FIG / "confusion_matrix_data.json", {"baseline": r1["baseline_confusion_matrix"], "selected": r1["selected_confusion_matrix"]})
    for name in ["time_cv_oof_predictions.csv", "severe_threshold_search.csv", "severe_weight_search.csv"]:
        target = REP / name
        assert not target.exists(), f"Refusing overwrite: {target}"
        shutil.copyfile(a / name, target)
    r1.update({"reproducibility": reproducibility, "audit": audit,
        "environment": json.loads((a / "pre_run_config.json").read_text(encoding="utf-8"))["versions"],
        "limitations": ["OOF optimization uses the same OOF for selection and reporting", "historical LGBM configuration selection included 2020-2021", "HDI is retrospective rather than publication-vintage data"]})
    target = REP / "time_cv_severe_optimization.json"
    assert not target.exists()
    exp.dump(target, r1)
    selected = candidates[candidates.candidate_id.eq(r1["recommended_development_candidate"])].iloc[0]
    baseline = candidates[candidates.candidate_id.eq("RF_T2")].iloc[0]
    delta = {metric: float(selected[metric] - baseline[metric]) for metric in
             ["macro_f1", "balanced_accuracy", "severe_precision", "severe_recall", "severe_f1", "severe_to_low", "severe_to_low_rate"]}
    locked_at = datetime.now(timezone.utc).isoformat()
    lock = {"locked_at_utc": locked_at, "scope": "Development candidates only; not production",
        "selected_candidate": r1["recommended_development_candidate"], "candidates": r1["candidates"],
        "thresholds": r1["threshold_selection"], "weight": r1["weight_selection"], "config": cfg,
        "config_sha256": exp.sha(exp.CFG_PATH), "script_sha256": exp.sha(HERE / "time_cv_oof_threshold_class_weight.py"),
        "test_evaluation_authorized": False, "maturity_used": False,
        "full_model_refit": "not performed; fold models not promoted; refit iteration rule fixed at 291 for LightGBM"}
    exp.dump(HERE / "development_candidate_lock.json", lock)
    yearly = pd.read_csv(HERE / "audit/development_yearly_counts.csv")
    fold_counts = pd.read_csv(HERE / "audit/fold_counts.csv")
    focus = ["model_id", "fold", "accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "quadratic_weighted_kappa", "severe_precision", "severe_recall", "severe_f1", "severe_to_low", "severe_to_low_rate"]
    base_folds = folds[folds.model_id.isin(["RF_T2", "LGBM_T2"])][focus]
    summary = tables["fold_metric_summary.csv"]
    stability_cols = ["model_id"] + [f"{m}_{stat}" for m in ["severe_recall", "severe_f1", "macro_f1"] for stat in ["mean", "std", "min", "max"]]
    stability = summary[summary.model_id.isin(["RF_T2", "LGBM_T2"])][stability_cols]
    ccols = ["candidate_id", "accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "severe_precision", "severe_recall", "severe_f1", "severe_to_low", "severe_to_low_rate"]
    threshold_text = "\n".join(f"- {mid}: " + ("没有满足 Precision≥0.45 的阈值；不放宽底线。" if row is None else
        f"阈值 {row['threshold']:.2f}；Precision={row['severe_precision']:.4f}、Recall={row['severe_recall']:.4f}、F1={row['severe_f1']:.4f}。") for mid, row in r1["threshold_selection"].items())
    threshold_sample = ts[(ts.fold == "pooled") & ts.threshold.isin([.20, .40, .60])][["model_id", "threshold", "severe_precision", "severe_recall", "severe_f1", "severe_to_low"]]
    threshold_max = ts[ts.fold == "pooled"].groupby("model_id").severe_precision.max()
    weight_text = "没有权重候选同时达到 Precision≥0.45 且 Severe F1 严格优于原基准，因此不保留优化权重及其组合；不降低底线、不搜索额外倍率。" if r1["weight_selection"] is None else f"保留 {r1['weight_selection']['model_id']}，组合只应用基准 RF 已选阈值，不重新寻找组合阈值。"
    stronger = "存在 Development 候选，但其改善具有指标间取舍，不代表已经获准替换正式模型。" if selected.candidate_id != "RF_T2" else "本次约束下未选出足以优先于默认 RF-T2 的候选；继续保留基准，不用 Test 反复寻找改善。"
    report = f"""# 第三阶段第二次补充：时间交叉验证与 Severe 类别优化

## 1. 目的、边界与预注册

回应指导老师关于 Severe 指标、模型对比和时间 Cross Validation 的建议。本轮只在 Development 内研究候选，原冻结 RF-T2 不变。没有新候选的 Test 评价，没有使用 Maturity 的特征或标签，没有系统/认证/数据库/部署改动。

预设配置 SHA-256：`{exp.sha(exp.CFG_PATH)}`；随机种子 20260803。阈值网格 0.20–0.60、步长 0.01；四个 Severe 倍率 1.25/1.5/2/2.5，加固定平衡字典倍率1.0对照。配置在拟合前保存，完整尝试均归档。第四阶段仍暂停。

## 2. 数据与可行性审计

Development 有标签事件 11590 条；因果历史频率来源含无标签事件，共 {audit['frequency_source_events']} 条。OOF 只覆盖 2014–2021 的3466条（Low 1025、Moderate 2195、Severe 246），不是全部11590条的OOF。2000–2013只作为训练起始窗口。

{md_table(yearly)}

### 扩展时间折

{md_table(fold_counts)}

四折无需调整，Severe验证数量均大于预设最少20条。每折训练年份严格早于验证年份，ID无交集，每条OOF事件只来自一个未训练过该事件的验证折。

### 时间特征与数据访问

独立计算 `upper(previous interval) < lower(current interval)` 的同国事件数，与冻结 historical_frequency 的差异为0；逐折截断未来日期后仍完全一致。不按Excel顺序累计、不让重叠年月精度事件互相提供虚构顺序。验证窗内过去已发生事件可进入后续事件的历史计数，这是顺序到达评估，不是验证窗首日对所有未来事件一次性预测。

共享CSV/XLSX文件通过年份/ID排除外期记录；物理上扫描了共享文件容器和排除字段，不声称从未触及其字节。Test/Maturity的特征与标签未进入实验数据帧或计算；模型训练只读取独立Development缓存。Test 948条的边界沿用既有冻结声明，本轮未重开Test预测表进行统计。

Magnitude沿用8个语义组，每折仅训练集拟合n/median/IQR；少于20条或IQR=0不生成z。所有15项特征均可构造，缺失按原方案处理。按折完整缺失表、统计量、类别词表和填充值已保存。

## 3. 模型与预处理口径

RF参数保持500棵树、max_depth=10、min_samples_leaf=5、max_features=0.5、balanced_subsample、random_state=20260803、n_jobs=-1。新增权重仅更改class_weight。

LightGBM复用真实历史 `LGBM-V2_P3_low_rate_balanced`：learning_rate=.03、num_leaves=63、max_depth=-1、min_child_samples=20、subsample=.8、subsample_freq=1、colsample_bytree=.7、reg_alpha=.1、reg_lambda=5。固定291轮，objective=multiclass、num_class=3，deterministic=True、force_col_wise=True。无逐折调参和early stopping。双方使用完全相同15项T2原始工程特征、折和三级评价代码。

RF为训练折拟合OneHot与中位数填补；LightGBM为训练折原生类别词表（明确UNKNOWN/MISSING）及NaN，平衡权重只从训练折类别数计算。预处理机制不同但信息范围相同。

历史LightGBM参数曾通过2020–2021 Validation选择，本轮复用它符合任务要求，但意味着这不是完全嵌套、对模型选择无偏的外层CV。历史HDI为回溯序列，也不等于具备当年发布时点的严格实时数据回测。

## 4. 默认模型逐折与OOF对比

{md_table(base_folds)}

各折等权平均、样本标准差（ddof=1）、最小最大值：

{md_table(stability)}

全部指标的各折原值、均值、标准差、最小最大值见 `fold_metrics.csv` 和 `fold_metric_summary.csv`。合并OOF指标按事件计算，不等同于各折指标平均。

稳定性不能只看一个标准差：RF的Severe Recall均值更高，两者Recall标准差接近；LightGBM的Severe F1标准差较小，但各折F1水平均较低。这不支持“LightGBM全面优于RF”，也不应声称RF在所有稳定性指标上都更好。

## 5. 阈值实验

规则：P(Severe)≥t判Severe，否则在Low/Moderate中取较高概率。仅用OOF，在Precision≥0.45下优先Recall，再比较Severe F1、Macro F1、Severe→Low比例；并列时选择相对默认argmax改变事件数更少的阈值，最后用稳定ID排序。argmax不是固定0.5边界，故不使用距离0.5近似其偏离。

{threshold_text}

代表性阈值点（完整网格仍保留）：

{md_table(threshold_sample)}

预定范围内最高Severe Precision：RF {threshold_max['RF_T2']:.4f}；LightGBM {threshold_max['LGBM_T2']:.4f}。这些最大值也不能替代联合约束下的候选选择，不扩展范围追加搜索。

0.45底线是实验中限制误报的预设要求，不是已获得专业认可的业务风险标准；仍可能有超过半数Severe预测为误报。所有41个阈值、两个模型、各折及合并OOF结果共410行全部保存。未校准输出概率不当作真实发生概率。

## 6. 类别权重与组合

scikit-learn 1.9.0中，balanced_subsample在每棵树抽样后平衡；固定字典按折训练N/(3*n_c)再乘Severe倍率。该版本sample/class weights参与bootstrap抽样，不能将固定字典倍率称为逐树balanced_subsample的精确相乘。倍率1.0对照用于分开解释机制变化与倍率变化。

{md_table(tables['severe_weight_search.csv'][['model_id','multiplier','severe_precision','severe_recall','severe_f1','macro_f1','balanced_accuracy','severe_to_low','eligible_for_retention']])}

{weight_text}

## 7. 开发阶段候选锁定

{md_table(candidates[ccols])}

按预定规则，推荐开发候选为 **{selected.candidate_id}**。相对RF-T2，OOF Severe Recall变化{delta['severe_recall']:+.4f}、Severe F1变化{delta['severe_f1']:+.4f}、Macro F1变化{delta['macro_f1']:+.4f}、Severe→Low数量变化{delta['severe_to_low']:+.0f}。{stronger}

此处阈值/权重选择和汇报使用同一OOF，存在选择乐观偏差，不是新的独立泛化结论。锁定时间：{locked_at}。仅锁定实验配方，未在全Development重拟合、未替换生产模型。默认基准的保留不表示它达到0.45底线；该底线用于接受新增优化候选。无可行优化方案时不自动推进Test；若论文需要原生三级LightGBM的最终独立对照，应另行批准一次性评价，而不是为寻找改善而重复测试。

## 8. 论文图表

以下全部是 **Development 时间CV OOF**，不是Test。纵轴从0开始，比例图统一0–1；使用色觉缺陷相对友好的颜色。PNG及底层数据均归档。

"""
    for name, caption in [("01_severe_recall_by_fold", "各折RF与LightGBM Severe Recall"), ("02_severe_f1_by_fold", "各折Severe F1"),
        ("03_severe_threshold_curve", "阈值与Precision/Recall/F1"), ("04_class_weight_curve", "权重倍率与Severe指标"),
        ("05_candidate_comparison", "主要候选综合指标"), ("06_rf_t2_oof_confusion", "RF-T2默认OOF混淆矩阵"),
        ("07_selected_oof_confusion", "推荐Development候选OOF混淆矩阵")]:
        report += f"\n![{caption}](../../ml_experiments/modeling/reports/figures/third_stage_severe/{name}.png)\n\n{caption}。\n"
    report += f"""
## 9. 时间序列问题边界与局限

year/event_month是给定灾害事件的分类输入，时间CV用于防止未来事件进入过去训练；模型不预测灾害是否发生。未来灾害次数或发生概率趋势是不同任务，需与指导老师另行确认。本轮没有ARIMA、Prophet、LSTM、SMOTE、两阶段模型或概率校准。

Severe每折仅49–72条，单个事件即可明显改变指标；不以细微差异声称显著优越。折之间训练集重叠、国家与时间相关，标准差只是描述量。OOF类别比例与未来年份未必相同。权重与阈值提高召回可能以误报和其他类别F1为代价；需结合完整混淆矩阵解释。

## 10. 复现与冻结边界

两次独立完整CV拟合（各28个模型拟合）结果一致：预测类别完全相同，概率最大绝对差{max_error:.3g}，指标差在1e-15内；特征顺序、类别词表、Magnitude统计量相同。第4折RF默认预测与原T2历史Validation类别完全相同，概率最大误差{historical_prob_error:.3g}。配置、代码、结果与原始输入哈希归档。

冻结原模型及API副本SHA-256均为 `{exp.EXPECTED_SHA}`；受保护文件{len(before)}个前后不变。Test未用于任何新候选评价/选择；Maturity特征标签未使用。项目状态仍为实验评估，正式Frozen边界不变，不更新project-status。

## 11. 可直接发给指导老师的说明

本次采用四折扩展窗口时间交叉验证，在2000–2021年Development内比较原生三级Random Forest和LightGBM，并预设Severe阈值与类别权重候选。基准RF-T2的OOF Severe Recall为{baseline.severe_recall:.4f}、F1为{baseline.severe_f1:.4f}、Macro F1为{baseline.macro_f1:.4f}。本轮没有新增优化方案满足预设Precision约束，因此保留RF-T2默认基准，而非宣称优化成功。提高Severe权重虽增加Recall，但Precision和F1下降。这些是Development实验结果，尚未进行新候选Test评价；最终RF-T2保持冻结。
"""
    doc = ROOT / "docs/stages/第三阶段_第二次补充_时间交叉验证与Severe优化.md"
    assert not doc.exists()
    doc.write_text(report, encoding="utf-8")
    lockdoc = ROOT / "docs/stages/第三阶段_Severe候选锁定记录.md"
    assert not lockdoc.exists()
    lockdoc.write_text(f"""# 第三阶段 Severe 开发候选锁定记录

锁定时间：{locked_at}。仅Development配方锁定，不是Production模型冻结。

推荐：**{selected.candidate_id}**。Test评价尚未授权；Maturity继续封存。

{md_table(candidates[ccols])}

阈值：
{threshold_text}

权重：{weight_text}

固定种子20260803。配置SHA-256：`{exp.sha(exp.CFG_PATH)}`。
训练脚本SHA-256：`{exp.sha(HERE / 'time_cv_oof_threshold_class_weight.py')}`。
完整参数、选择规则、实际权重、预处理统计、代码版本和OOF见独立实验目录及 `development_candidate_lock.json`。

阈值/权重由相同OOF选择与展示，不作为独立Test结果。未经批准不读取Test评价新候选；不改变原冻结RF-T2，不恢复第四阶段。
""", encoding="utf-8")
    files = [p for p in HERE.rglob("*") if p.is_file() and not any(x in p.parts for x in [".dependencies", "__pycache__"])]
    files += list(FIG.glob("*")) + [doc, lockdoc, target] + [REP / n for n in ["time_cv_oof_predictions.csv", "severe_threshold_search.csv", "severe_weight_search.csv"]]
    exp.dump(HERE / "manifest.json", {"created_at_utc": locked_at, "frozen_model_sha256": exp.EXPECTED_SHA,
        "files": {p.relative_to(ROOT).as_posix(): exp.sha(p) for p in sorted(set(files))},
        "test_evaluated": False, "maturity_features_labels_used": False})
    print(candidates[ccols].to_string(index=False))
    print(json.dumps(reproducibility, indent=2))


if __name__ == "__main__": main()
