const CHART_GREEN = 'rgba(124, 255, 155, 0.88)'
const CHART_GREEN_DIM = 'rgba(124, 255, 155, 0.28)'
const CHART_AMBER = 'rgba(214, 168, 79, 0.9)'
const CHART_GRID = 'rgba(92, 255, 137, 0.12)'
const CHART_TEXT = 'rgba(184, 245, 194, 0.62)'

const SEVERITY_COLORS = {
  critical: 'rgba(255, 110, 110, 0.9)',
  high: 'rgba(255, 180, 90, 0.9)',
  medium: 'rgba(214, 168, 79, 0.82)',
  low: 'rgba(124, 255, 155, 0.55)',
}

function escapeText(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function truncateLabel(text, max = 8) {
  const value = String(text || '')
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function mountSvg(container, width, height, inner) {
  container.innerHTML = `
    <svg class="terminal-chart__svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-hidden="true">
      ${inner}
    </svg>
  `
}

function gridLines(width, height, pad, rows = 4) {
  let lines = ''
  for (let i = 0; i <= rows; i++) {
    const y = pad.t + ((height - pad.t - pad.b) * i) / rows
    lines += `<line x1="${pad.l}" y1="${y}" x2="${width - pad.r}" y2="${y}" stroke="${CHART_GRID}" stroke-width="1" stroke-dasharray="3 5" />`
  }
  return lines
}

export function renderVerticalBarChart(container, items, { color = CHART_GREEN, maxValue } = {}) {
  if (!container) return
  const width = 360
  const height = 220
  const pad = { t: 16, r: 12, b: 42, l: 12 }
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b

  if (!items.length) {
    mountSvg(container, width, height, `<text x="${width / 2}" y="${height / 2}" fill="${CHART_TEXT}" font-size="11" text-anchor="middle">NO DATA</text>`)
    return
  }

  const max = maxValue ?? Math.max(...items.map((d) => d.value), 1)
  const gap = 10
  const barW = (plotW - gap * (items.length - 1)) / items.length

  let bars = gridLines(width, height, pad)
  items.forEach((item, i) => {
    const barH = (item.value / max) * plotH
    const x = pad.l + i * (barW + gap)
    const y = pad.t + plotH - barH
    bars += `
      <rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${color}" opacity="0.82">
        <animate attributeName="height" from="0" to="${barH}" dur="0.5s" fill="freeze" />
        <animate attributeName="y" from="${pad.t + plotH}" to="${y}" dur="0.5s" fill="freeze" />
      </rect>
      <text x="${x + barW / 2}" y="${height - 18}" fill="${CHART_TEXT}" font-size="9" text-anchor="middle">${escapeText(truncateLabel(item.label, 6))}</text>
      <text x="${x + barW / 2}" y="${y - 4}" fill="${CHART_GREEN}" font-size="9" text-anchor="middle">${item.value}</text>
    `
  })

  mountSvg(container, width, height, bars)
}

export function renderHorizontalBarChart(container, items, { color = CHART_GREEN } = {}) {
  if (!container) return
  const width = 360
  const rowH = 28
  const pad = { t: 12, r: 36, b: 12, l: 88 }
  const height = pad.t + pad.b + items.length * rowH

  if (!items.length) {
    mountSvg(container, width, 120, `<text x="${width / 2}" y="60" fill="${CHART_TEXT}" font-size="11" text-anchor="middle">NO DATA</text>`)
    return
  }

  const max = Math.max(...items.map((d) => d.value), 1)
  const plotW = width - pad.l - pad.r
  let content = ''

  items.forEach((item, i) => {
    const y = pad.t + i * rowH
    const barW = (item.value / max) * plotW
    content += `
      <text x="${pad.l - 8}" y="${y + 16}" fill="${CHART_TEXT}" font-size="10" text-anchor="end">${escapeText(truncateLabel(item.label, 10))}</text>
      <rect x="${pad.l}" y="${y + 4}" width="${plotW}" height="14" fill="${CHART_GREEN_DIM}" opacity="0.35" />
      <rect x="${pad.l}" y="${y + 4}" width="${barW}" height="14" fill="${color}" opacity="0.85" />
      <text x="${pad.l + plotW + 6}" y="${y + 15}" fill="${CHART_GREEN}" font-size="9">${item.value}</text>
    `
  })

  mountSvg(container, width, height, content)
}

export function renderLineChart(container, items) {
  if (!container) return
  const width = 360
  const height = 220
  const pad = { t: 18, r: 14, b: 40, l: 14 }
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b

  if (!items.length) {
    mountSvg(container, width, height, `<text x="${width / 2}" y="${height / 2}" fill="${CHART_TEXT}" font-size="11" text-anchor="middle">NO DATA</text>`)
    return
  }

  const max = Math.max(...items.map((d) => d.value), 1)
  const step = items.length > 1 ? plotW / (items.length - 1) : 0

  const points = items.map((item, i) => {
    const x = pad.l + i * step
    const y = pad.t + plotH - (item.value / max) * plotH
    return { x, y, item }
  })

  const polyline = points.map((p) => `${p.x},${p.y}`).join(' ')
  let content = gridLines(width, height, pad)

  content += `<polyline points="${polyline}" fill="none" stroke="${CHART_GREEN}" stroke-width="2" stroke-linejoin="round" opacity="0.9" />`

  points.forEach(({ x, y, item }) => {
    content += `
      <circle cx="${x}" cy="${y}" r="3.5" fill="${CHART_AMBER}" stroke="${CHART_GREEN}" stroke-width="1.5" />
      <text x="${x}" y="${height - 14}" fill="${CHART_TEXT}" font-size="8" text-anchor="middle">${escapeText(truncateLabel(item.label, 7))}</text>
      <text x="${x}" y="${y - 7}" fill="${CHART_GREEN}" font-size="8" text-anchor="middle">${item.value}</text>
    `
  })

  mountSvg(container, width, height, content)
}

export function renderSeverityChart(container, items) {
  const colored = items.map((item) => ({
    ...item,
    color: SEVERITY_COLORS[item.key] || CHART_GREEN,
  }))

  if (!container) return
  const width = 360
  const height = 220
  const pad = { t: 16, r: 12, b: 42, l: 12 }
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b

  if (!colored.length) {
    mountSvg(container, width, height, `<text x="${width / 2}" y="${height / 2}" fill="${CHART_TEXT}" font-size="11" text-anchor="middle">NO DATA</text>`)
    return
  }

  const max = Math.max(...colored.map((d) => d.value), 1)
  const gap = 12
  const barW = (plotW - gap * (colored.length - 1)) / colored.length
  let bars = gridLines(width, height, pad)

  colored.forEach((item, i) => {
    const barH = (item.value / max) * plotH
    const x = pad.l + i * (barW + gap)
    const y = pad.t + plotH - barH
    bars += `
      <rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${item.color}" opacity="0.88" />
      <text x="${x + barW / 2}" y="${height - 18}" fill="${CHART_TEXT}" font-size="9" text-anchor="middle">${escapeText(truncateLabel(item.label, 5))}</text>
      <text x="${x + barW / 2}" y="${y - 4}" fill="${CHART_GREEN}" font-size="9" text-anchor="middle">${item.value}</text>
    `
  })

  mountSvg(container, width, height, bars)
}
