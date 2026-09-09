import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

const path = new URL('../src/data/model-registry.json', import.meta.url)
const registry = JSON.parse(await readFile(path, 'utf8'))
const requiredModelKeys = ['id', 'displayName', 'algorithm', 'status', 'evaluationScope', 'labelSet', 'featureSet', 'metrics', 'experimentSource']
const allowedStatuses = new Set(['Production', 'Candidate', 'Historical', 'Baseline', 'Rejected'])
const allowedScopes = new Set(['historicalValidation', 'developmentOof', 'lockedTest'])

if (registry.schemaVersion !== 1 || !Array.isArray(registry.models)) throw new Error('Invalid registry root')
if (!registry.generatedFrom.every((source) => registry.sourceHashes?.[source])) throw new Error('Source traceability is incomplete')
for (const model of registry.models) {
  for (const key of requiredModelKeys) if (!(key in model)) throw new Error(`${model.id || 'unknown'} missing ${key}`)
  if (!allowedStatuses.has(model.status)) throw new Error(`Invalid status: ${model.status}`)
  if (!allowedScopes.has(model.evaluationScope)) throw new Error(`Invalid evaluation scope: ${model.evaluationScope}`)
}
const production = registry.models.filter((model) => model.status === 'Production')
if (production.length !== 1 || production[0].id !== registry.productionModelId) throw new Error('RF-T2 must be the sole Production model')
if (production[0].artifactHash !== 'c4960347d423b1b46065c8e2fc57e1e1656fae11e1198af2fe5c6a734392a9d4') throw new Error('Frozen checksum mismatch')
if (registry.models.find((model) => model.id === 'lgbm-t2')?.evaluationScope !== 'developmentOof') throw new Error('LightGBM cannot expose a Test scope')
const expectedWeights = [
  [1, 0.23076923076923078, 0.524390243902439, 0.3204968944099379],
  [1.25, 0.19562243502051985, 0.5813008130081301, 0.29273285568065505],
  [1.5, 0.18116805721096543, 0.6178861788617886, 0.280184331797235],
  [2, 0.15529622980251345, 0.7032520325203252, 0.25441176470588234],
  [2.5, 0.1388690050107373, 0.7886178861788617, 0.2361533779671333],
]
if (registry.experiments.weightSearch.length !== expectedWeights.length) throw new Error('Weight experiment rows are incomplete')
expectedWeights.forEach(([multiplier, precision, recall, f1], index) => {
  const row = registry.experiments.weightSearch[index]
  if ([row.weightMultiplier - multiplier, row.severePrecision - precision, row.severeRecall - recall, row.severeF1 - f1].some((difference) => Math.abs(difference) > 1e-15)) throw new Error(`Weight experiment mismatch at row ${index}`)
})

const sha256 = createHash('sha256').update(await readFile(path)).digest('hex')
console.log(`model registry valid: ${registry.models.length} models, 1 Production, sha256=${sha256}`)
