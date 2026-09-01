import assert from 'node:assert/strict'
import { buildPredictionSummary, fetchImpactOptions, formatReferenceFactors, validateImpactOptions } from '../src/pages/user/impactAnalysis.js'

const valid = {
  success: true,
  countries: [{ code: 'CHN', name: 'China', region: 'Asia' }],
  disaster_types: [{ type: 'Flood', subtypes: ['Flood (General)'] }],
  magnitude_scales: ['Km2'],
  magnitude_groups: [{ group_key: 'Flood | Km2', group_name: 'Flood', disaster_type: 'Flood', magnitude_scale: 'Km2', unit_label: 'km²', eligible: true, sample_count: 100, grouping_strategy: 'disaster_type+magnitude_scale', references: [{ label: '中位参考值', value: 1000 }] }],
}
const jsonResponse = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

assert.equal(validateImpactOptions(valid), valid)
assert.throws(() => validateImpactOptions({ ...valid, countries: [] }), /国家或地区列表为空/)
assert.throws(() => validateImpactOptions({ ...valid, disaster_types: 'bad' }), /灾害类型列表为空/)
assert.throws(() => validateImpactOptions({ ...valid, magnitude_scales: null }), /强度量表结构错误/)

let calls = 0
const first = await fetchImpactOptions({ fetchImpl: async () => { calls += 1; return jsonResponse(valid) } })
const second = await fetchImpactOptions({ fetchImpl: async () => { calls += 1; return jsonResponse(valid) } })
assert.deepEqual(first, valid)
assert.deepEqual(second, valid)
assert.equal(calls, 2)

await assert.rejects(
  fetchImpactOptions({ fetchImpl: async () => new Response('<html></html>', { status: 200, headers: { 'Content-Type': 'text/html' } }) }),
  (error) => error.code === 'OPTIONS_NOT_JSON' && error.status === 200,
)
await assert.rejects(
  fetchImpactOptions({ fetchImpl: async () => jsonResponse({ success: false, error: { code: 'OPTIONS_UNAVAILABLE', message: '暂时不可用' } }, 500) }),
  (error) => error.code === 'OPTIONS_UNAVAILABLE' && error.status === 500,
)

assert.equal(
  buildPredictionSummary({ prediction: { probabilities: { Low: 0.2, Moderate: 0.38, Severe: 0.42 } } }),
  '“严重影响”与“中等影响”的输出概率较为接近，建议结合完整的概率分布理解本次结果。',
)
assert.equal(
  buildPredictionSummary({ prediction: { probabilities: { Low: 0.7, Moderate: 0.2, Severe: 0.1 } } }),
  '根据历史档案的相似特征，本次输入更接近“低影响”等级。',
)
assert.deepEqual(
  formatReferenceFactors(['冻结历史档案频次：423', '事件年度HDI背景值：0.788', 'Magnitude同语义组内相对位置：-0.243（不可跨量表比较）', '日期仅有年份，月份作为缺失处理']),
  ['同类历史档案：423条', '事发年份人类发展指数（HDI）：0.788', '灾害强度：在同类历史记录中接近一般水平'],
)

console.log(JSON.stringify({ passed: 12, calls }))
