import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { parse } from 'csv-parse/sync'

const root = resolve(import.meta.dirname, '..')
const source = (path) => resolve(root, path)
const readJson = async (path) => JSON.parse(await readFile(source(path), 'utf8'))
const readCsv = async (path) => parse(await readFile(source(path), 'utf8'), { bom: true, columns: true, skip_empty_lines: true })
const number = (value) => value === '' || value == null ? null : Number(value)
const pick = (row) => Object.fromEntries([
  'accuracy', 'balanced_accuracy', 'macro_f1', 'weighted_f1',
  'severe_precision', 'severe_recall', 'severe_f1',
].map((key) => [key, number(row?.[key])]))

const paths = {
  rfCandidates: 'ml_experiments/modeling/reports/model_comparison.csv',
  threeClass: 'ml_experiments/modeling/three_class/reports/metrics.csv',
  finalTest: 'ml_experiments/modeling/three_class/final_t2/reports/test_metrics.csv',
  finalPerClass: 'ml_experiments/modeling/three_class/final_t2/reports/per_class_metrics.csv',
  finalConfig: 'ml_experiments/modeling/three_class/final_t2/artifacts/locked_final_config.json',
  finalManifest: 'ml_experiments/modeling/three_class/final_t2/manifest.json',
  ci: 'ml_experiments/modeling/reports/third_stage_supplement_ci.json',
  oof: 'ml_experiments/modeling/reports/figures/third_stage_severe/pooled_oof_metrics.csv',
  folds: 'ml_experiments/modeling/reports/figures/third_stage_severe/fold_metrics.csv',
  threshold: 'ml_experiments/modeling/time_cv_severe_optimization/run1/severe_threshold_search.csv',
  weights: 'ml_experiments/modeling/time_cv_severe_optimization/run1/severe_weight_search.csv',
}

const [rfRows, tRows, testRows, perClass, config, manifest, ci, oofRows, foldRows, thresholdRows, weightRows] = await Promise.all([
  readCsv(paths.rfCandidates), readCsv(paths.threeClass), readCsv(paths.finalTest), readCsv(paths.finalPerClass),
  readJson(paths.finalConfig), readJson(paths.finalManifest), readJson(paths.ci), readCsv(paths.oof), readCsv(paths.folds),
  readCsv(paths.threshold), readCsv(paths.weights),
])

const find = (rows, predicate, label) => {
  const row = rows.find(predicate)
  if (!row) throw new Error(`Missing audited source row: ${label}`)
  return row
}
const finalSevere = find(perClass, (r) => r.experiment_id === 'final_T2' && r.split === 'test' && r.class === 'Severe', 'final T2 Severe')
const finalMetrics = { ...pick(testRows[0]), severe_precision: number(finalSevere.precision), severe_recall: number(finalSevere.recall), severe_f1: number(finalSevere.f1) }
const finalHash = config.locked_configuration.input_hashes['ml_experiments/modeling/three_class/artifacts/T2_random_forest_pipeline.joblib']
const frozenHash = ci.inputs.frozen_model_sha256
if (frozenHash !== 'c4960347d423b1b46065c8e2fc57e1e1656fae11e1198af2fe5c6a734392a9d4') throw new Error('Frozen model checksum mismatch')
if (ci.test_audit.rows !== 948) throw new Error('Unexpected frozen Test row count')

const rfV1 = find(rfRows, (r) => r.model_id === 'RF-V1_C09', 'RF-V1_C09')
const rfV2 = find(rfRows, (r) => r.model_id === 'RF-V2_C09', 'RF-V2_C09')
const dummy = find(rfRows, (r) => r.model_id === 'Dummy_prior', 'Dummy_prior')
const t0 = find(tRows, (r) => r.experiment_id === 'T0' && r.split === 'validation', 'T0 validation')
const oofRf = find(oofRows, (r) => r.model_id === 'RF_T2', 'RF_T2 OOF')
const oofLgbm = find(oofRows, (r) => r.model_id === 'LGBM_T2', 'LGBM_T2 OOF')

const chartFolds = foldRows.filter((r) => ['RF_T2', 'LGBM_T2'].includes(r.model_id)).map((r) => ({
  model: r.model_id, fold: Number(r.fold), severeRecall: number(r.severe_recall), severeF1: number(r.severe_f1),
}))
const pooled = [oofRf, oofLgbm].map((r) => ({ model: r.model_id, ...pick(r) }))
const pooledThresholds = thresholdRows.filter((r) => r.fold === 'pooled').map((r) => ({
  threshold: number(r.threshold), severePrecision: number(r.severe_precision), severeRecall: number(r.severe_recall), severeF1: number(r.severe_f1), macroF1: number(r.macro_f1),
}))
const pooledWeights = weightRows.map((r) => ({
  model: r.model_id, weightMultiplier: number(r.multiplier), severePrecision: number(r.severe_precision), severeRecall: number(r.severe_recall), severeF1: number(r.severe_f1), macroF1: number(r.macro_f1),
}))

const registry = {
  schemaVersion: 1,
  generatedFrom: Object.values(paths),
  sourceHashes: Object.fromEntries(await Promise.all(Object.values(paths).map(async (path) => [path, createHash('sha256').update(await readFile(source(path))).digest('hex')]))),
  evaluationScopes: {
    historicalValidation: '历史 Validation；仅同一标签与划分内比较',
    developmentOof: 'Development 2000—2021 时间交叉验证 OOF；未读取 Test 或 Maturity',
    lockedTest: '模型锁定后独立 Test 2022—2023；948 条',
  },
  productionModelId: 'rf-t2-final',
  models: [
    { id: 'dummy-prior-4c', displayName: 'Dummy Prior 基线', algorithm: 'DummyClassifier', status: 'Baseline', evaluationScope: 'historicalValidation', labelSet: '四分类', featureSet: '无', metrics: pick(dummy), conclusion: '仅反映类别先验，作为早期四分类下界。', experimentSource: paths.rfCandidates },
    { id: 'rf-v1-4c', displayName: 'Random Forest RF-V1', algorithm: 'Random Forest', status: 'Historical', evaluationScope: 'historicalValidation', labelSet: '四分类', featureSet: 'RF-V1', metrics: pick(rfV1), conclusion: '早期四分类基础特征方案，仅作历史对照。', experimentSource: paths.rfCandidates },
    { id: 'rf-v2-4c', displayName: 'Random Forest RF-V2', algorithm: 'Random Forest', status: 'Historical', evaluationScope: 'historicalValidation', labelSet: '四分类', featureSet: 'RF-V2', metrics: pick(rfV2), conclusion: '早期四分类月份增强方案，不能与三级模型直接排名。', experimentSource: paths.rfCandidates },
    { id: 'rf-t0-3c', displayName: 'Random Forest T0 消融基线', algorithm: 'Random Forest', status: 'Baseline', evaluationScope: 'historicalValidation', labelSet: '三级', featureSet: 'T0 基础特征', metrics: pick(t0), conclusion: '三级分类基础特征消融对照。', experimentSource: paths.threeClass },
    { id: 'lgbm-t2', displayName: 'LightGBM T2', algorithm: 'LightGBM', status: 'Candidate', evaluationScope: 'developmentOof', labelSet: '三级', featureSet: 'T2', metrics: pick(oofLgbm), conclusion: '时间折表现有波动，合并 OOF 未形成替换 RF-T2 的稳定综合优势。', caveat: '参数曾根据历史验证集选择，时间交叉验证对比并非完全嵌套的无偏模型选择评估。', experimentSource: paths.oof },
    { id: 'rf-t2-final', displayName: 'Random Forest T2', algorithm: 'Random Forest', status: 'Production', evaluationScope: 'lockedTest', labelSet: '三级', featureSet: 'T2 / 15项锁定特征', metrics: finalMetrics, trainPeriod: 'Development 2000—2021', testPeriod: 'Test 2022—2023', artifactHash: frozenHash, sourceArtifactHash: finalHash, conclusion: '唯一正式模型；冻结 Pipeline 已通过一致性验证。', experimentSource: paths.finalManifest, parameters: config.locked_configuration.rf_params },
  ],
  experiments: {
    pooledOof: pooled,
    temporalFolds: chartFolds,
    testConfusionMatrix: { labels: ci.test_audit.confusion_matrix_labels, values: ci.test_audit.confusion_matrix },
    bootstrapIntervals: ci.bootstrap_intervals,
    severeRecallWilson: ci.severe_recall_wilson,
    thresholdSearch: pooledThresholds,
    weightSearch: pooledWeights,
    conclusions: [
      'RF-T2在合并Development OOF上的Macro F1、Balanced Accuracy和Severe F1均高于历史LightGBM T2。',
      '两种模型的Severe表现随时间折波动，不能将单一时间折结果解释为稳定优势。',
      '提高Severe权重可提升Recall，但同时显著降低Precision、F1与整体Macro F1。',
      '阈值实验未在预设约束下找到可接受候选，因此保持冻结RF-T2。',
    ],
  },
  frozenModel: {
    name: 'Random Forest T2', classes: ['Low', 'Moderate', 'Severe'], featureCount: 15,
    sha256: frozenHash, development: '2000—2021', test: '2022—2023', testRows: ci.test_audit.rows,
    integrity: manifest.validation?.all_passed === false ? 'CHECK REQUIRED' : 'VERIFIED',
    scope: '灾害事件影响等级辅助分析；不是灾害发生预测或实时预警，不代替专业判断；不使用灾后伤亡结果作为输入。',
  },
}

const output = source('src/data/model-registry.json')
await mkdir(dirname(output), { recursive: true })
await writeFile(output, `${JSON.stringify(registry, null, 2)}\n`, 'utf8')
const sha = createHash('sha256').update(await readFile(output)).digest('hex')
console.log(`model registry generated: ${registry.models.length} models, sha256=${sha}`)
