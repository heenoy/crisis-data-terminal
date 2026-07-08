export function parseStatNumber(value) {
  if (value == null || value === '') return null
  const n = Number(value)
  return Number.isNaN(n) ? null : n
}

export function statNumberOrZero(value) {
  return parseStatNumber(value) ?? 0
}

export function formatStatNumber(value) {
  const n = parseStatNumber(value)
  if (n == null) return '未记录'
  if (n === 0) return '0'
  if (n >= 100000000) return `${(n / 100000000).toFixed(1)}亿`
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return n.toLocaleString('zh-CN')
}
