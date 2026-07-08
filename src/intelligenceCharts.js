import { labelCountry, labelDisasterType } from './disasterEvents.js'

const C = {
  bg: '#020805',
  panel: '#06150d',
  green: '#39ff88',
  greenDim: 'rgba(57, 255, 136, 0.22)',
  greenMid: 'rgba(57, 255, 136, 0.55)',
  text: '#5f8f70',
  textBright: 'rgba(57, 255, 136, 0.82)',
  warn: '#ffb347',
  danger: '#ff5555',
  grid: 'rgba(57, 255, 136, 0.06)',
  land: 'rgba(30, 80, 48, 0.45)',
  ocean: '#031009',
}

const GREEN_PALETTE = ['#39ff88', '#2ecc71', '#27a85c', '#1f8449', '#186038', '#124628']

const MAP_TIER = {
  normal: { fill: C.green, stroke: 'rgba(57,255,136,0.35)', glow: 'rgba(57,255,136,0.45)' },
  high: { fill: C.warn, stroke: 'rgba(255,179,71,0.4)', glow: 'rgba(255,179,71,0.35)' },
  critical: { fill: C.danger, stroke: 'rgba(255,85,85,0.45)', glow: 'rgba(255,85,85,0.4)' },
}

const LANDMASSES = [
  { cx: 0.18, cy: 0.34, rx: 0.11, ry: 0.2 },
  { cx: 0.24, cy: 0.66, rx: 0.07, ry: 0.16 },
  { cx: 0.48, cy: 0.36, rx: 0.1, ry: 0.14 },
  { cx: 0.5, cy: 0.58, rx: 0.09, ry: 0.2 },
  { cx: 0.68, cy: 0.34, rx: 0.16, ry: 0.18 },
  { cx: 0.74, cy: 0.62, rx: 0.08, ry: 0.1 },
  { cx: 0.84, cy: 0.72, rx: 0.09, ry: 0.08 },
]

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

function mountSvg(container, width, height, inner, className = 'terminal-chart__svg') {
  container.innerHTML = `
    <svg class="${className}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-hidden="true">
      <defs>
        <filter id="intel-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="intel-radar" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(57,255,136,0.08)" />
          <stop offset="70%" stop-color="rgba(57,255,136,0.02)" />
          <stop offset="100%" stop-color="rgba(2,8,5,0)" />
        </radialGradient>
      </defs>
      ${inner}
    </svg>
  `
}

function gridLines(width, height, pad, rows = 4) {
  let lines = ''
  for (let i = 0; i <= rows; i++) {
    const y = pad.t + ((height - pad.t - pad.b) * i) / rows
    lines += `<line x1="${pad.l}" y1="${y}" x2="${width - pad.r}" y2="${y}" stroke="${C.grid}" stroke-width="1" stroke-dasharray="2 8" />`
  }
  return lines
}

function projectLonLat(lng, lat, width, height, pad) {
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b
  const x = pad.l + ((lng + 180) / 360) * plotW
  const y = pad.t + ((90 - lat) / 180) * plotH
  return { x, y }
}

function formatTooltipNumber(value) {
  const n = Number(value) || 0
  return n.toLocaleString('zh-CN')
}

function mapPointTier(point) {
  const casualties = Number(point.casualties) || 0
  const affected = Number(point.affected_population) || 0
  if (casualties >= 500 || affected >= 500000) return 'critical'
  if (casualties >= 20 || affected >= 20000) return 'high'
  return 'normal'
}

function formatCompact(value) {
  if (value >= 100000000) return `${(value / 100000000).toFixed(1)}亿`
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`
  return String(value)
}

export function renderGlobalDisasterMap(container, points) {
  if (!container) return () => {}

  const width = 720
  const height = 360
  const pad = { t: 18, r: 16, b: 28, l: 16 }
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b
  const cx = pad.l + plotW / 2
  const cy = pad.t + plotH / 2

  let land = `<rect x="${pad.l}" y="${pad.t}" width="${plotW}" height="${plotH}" fill="${C.ocean}" />`
  land += `<rect x="${pad.l}" y="${pad.t}" width="${plotW}" height="${plotH}" fill="url(#intel-radar)" />`

  for (let r = 0.2; r <= 1; r += 0.2) {
    land += `<circle cx="${cx}" cy="${cy}" r="${(plotW * r) / 2}" fill="none" stroke="${C.grid}" stroke-width="1" opacity="0.35" />`
  }

  for (let lon = -180; lon <= 180; lon += 30) {
    const x = pad.l + ((lon + 180) / 360) * plotW
    land += `<line x1="${x}" y1="${pad.t}" x2="${x}" y2="${pad.t + plotH}" stroke="${C.grid}" stroke-width="1" stroke-dasharray="2 8" opacity="0.5" />`
  }
  for (let lat = -60; lat <= 60; lat += 30) {
    const y = pad.t + ((90 - lat) / 180) * plotH
    land += `<line x1="${pad.l}" y1="${y}" x2="${pad.l + plotW}" y2="${y}" stroke="${C.grid}" stroke-width="1" stroke-dasharray="2 8" opacity="0.5" />`
  }

  LANDMASSES.forEach((shape) => {
    const lx = pad.l + shape.cx * plotW
    const ly = pad.t + shape.cy * plotH
    land += `<ellipse cx="${lx}" cy="${ly}" rx="${shape.rx * plotW}" ry="${shape.ry * plotH}" fill="${C.land}" stroke="rgba(57,255,136,0.1)" stroke-width="1" />`
  })

  const validPoints = (points || []).filter((p) => p.lat != null && p.lng != null)
  let markers = ''
  validPoints.forEach((point, index) => {
    const { x, y } = projectLonLat(point.lng, point.lat, width, height, pad)
    const tier = mapPointTier(point)
    const style = MAP_TIER[tier]
    const r = tier === 'critical' ? 5.5 : tier === 'high' ? 4.5 : 3.5
    markers += `
      <circle class="intel-map-point intel-map-point--${tier}" data-index="${index}" cx="${x}" cy="${y}" r="${r}" fill="${style.fill}" stroke="${style.stroke}" stroke-width="1.2" opacity="0.9" filter="url(#intel-glow)">
        <title>${escapeText(point.title)}</title>
      </circle>
    `
  })

  land += `
    <text x="${pad.l + 4}" y="${pad.t + 12}" fill="${C.text}" font-size="8" opacity="0.7">180°W</text>
    <text x="${pad.l + plotW - 28}" y="${pad.t + 12}" fill="${C.text}" font-size="8" opacity="0.7">180°E</text>
    <text x="${pad.l + 4}" y="${pad.t + plotH - 4}" fill="${C.text}" font-size="8" opacity="0.7">60°S</text>
    <text x="${pad.l + 4}" y="${pad.t + 16}" fill="${C.text}" font-size="8" opacity="0.7">60°N</text>
  `

  mountSvg(container, width, height, land + markers, 'terminal-chart__svg intel-map-svg')

  const tooltip = document.createElement('div')
  tooltip.className = 'intel-map-tooltip'
  tooltip.hidden = true
  container.appendChild(tooltip)

  const svg = container.querySelector('svg')
  const circles = container.querySelectorAll('.intel-map-point')

  function showTooltip(event, point) {
    const tier = mapPointTier(point)
    tooltip.hidden = false
    tooltip.dataset.tier = tier
    tooltip.innerHTML = `
      <strong>${escapeText(point.title)}</strong>
      <span>${escapeText(labelDisasterType(point.disaster_type))} · ${escapeText(labelCountry(point.country))}</span>
      <span>死亡人数：${formatTooltipNumber(point.casualties)}</span>
      <span>受影响人数：${formatTooltipNumber(point.affected_population)}</span>
      <span>坐标：${point.lat.toFixed(2)}，${point.lng.toFixed(2)}</span>
    `
    const rect = container.getBoundingClientRect()
    const x = event.clientX - rect.left + 12
    const y = event.clientY - rect.top + 12
    tooltip.style.left = `${Math.min(x, rect.width - 220)}px`
    tooltip.style.top = `${Math.min(y, rect.height - 120)}px`
  }

  function hideTooltip() {
    tooltip.hidden = true
  }

  circles.forEach((circle) => {
    const index = Number(circle.dataset.index)
    const point = validPoints[index]
    if (!point) return
    circle.addEventListener('mouseenter', (e) => showTooltip(e, point))
    circle.addEventListener('mousemove', (e) => showTooltip(e, point))
    circle.addEventListener('mouseleave', hideTooltip)
    circle.addEventListener('focus', (e) => showTooltip(e, point))
    circle.addEventListener('blur', hideTooltip)
    circle.setAttribute('tabindex', '0')
    circle.setAttribute('role', 'button')
    circle.setAttribute('aria-label', point.title)
  })

  return () => {
    tooltip.remove()
    svg?.replaceWith(svg.cloneNode(true))
  }
}

export function renderDualLineChart(container, seriesA, seriesB, { labelA = 'EVENTS', labelB = 'AFFECTED' } = {}) {
  if (!container) return

  const width = 680
  const height = 300
  const pad = { t: 28, r: 52, b: 36, l: 44 }
  const plotW = width - pad.l - pad.r
  const plotH = height - pad.t - pad.b

  if (!seriesA.length) {
    mountSvg(container, width, height, `<text x="${width / 2}" y="${height / 2}" fill="${C.text}" font-size="11" text-anchor="middle">暂无数据</text>`)
    return
  }

  const maxA = Math.max(...seriesA.map((d) => d.value), 1)
  const maxB = Math.max(...seriesB.map((d) => d.value), 1)
  const step = seriesA.length > 1 ? plotW / (seriesA.length - 1) : 0

  const pointsA = seriesA.map((item, i) => {
    const x = pad.l + i * step
    const y = pad.t + plotH - (item.value / maxA) * plotH
    return { x, y, item }
  })

  const pointsB = seriesB.map((item, i) => {
    const x = pad.l + i * step
    const y = pad.t + plotH - (item.value / maxB) * plotH
    return { x, y, item }
  })

  let content = gridLines(width, height, pad, 5)
  content += `<polyline points="${pointsB.map((p) => `${p.x},${p.y}`).join(' ')}" fill="none" stroke="${C.greenMid}" stroke-width="1.5" opacity="0.65" stroke-dasharray="4 5" />`
  content += `<polyline points="${pointsA.map((p) => `${p.x},${p.y}`).join(' ')}" fill="none" stroke="${C.green}" stroke-width="2" opacity="0.9" />`

  pointsA.forEach(({ x, y, item }, i) => {
    content += `<circle cx="${x}" cy="${y}" r="2.5" fill="${C.green}" />`
    if (i % Math.ceil(seriesA.length / 8) === 0 || i === seriesA.length - 1) {
      content += `<text x="${x}" y="${height - 12}" fill="${C.text}" font-size="7" text-anchor="middle" opacity="0.75">${escapeText(truncateLabel(item.label, 6))}</text>`
    }
  })

  pointsB.forEach(({ x, y }) => {
    content += `<circle cx="${x}" cy="${y}" r="2" fill="${C.greenMid}" />`
  })

  content += `
    <text x="${width - pad.r + 6}" y="${pad.t + 8}" fill="${C.green}" font-size="7">${labelA}</text>
    <text x="${width - pad.r + 6}" y="${pad.t + 18}" fill="${C.text}" font-size="7">${labelB}</text>
  `

  mountSvg(container, width, height, content)
}

export function renderDonutChart(container, items) {
  if (!container) return

  const width = 360
  const height = 300
  const cx = width / 2
  const cy = height / 2 - 10
  const outerR = 92
  const innerR = 58

  const total = items.reduce((sum, item) => sum + item.value, 0)
  if (!total) {
    mountSvg(container, width, height, `<text x="${width / 2}" y="${height / 2}" fill="${C.text}" font-size="11" text-anchor="middle">暂无数据</text>`)
    return
  }

  const maxItem = items.reduce((best, item) => (item.value > best.value ? item : best), items[0])
  let angle = -Math.PI / 2
  let arcs = ''
  let legend = ''

  items.forEach((item, i) => {
    const slice = (item.value / total) * Math.PI * 2
    const x1 = cx + outerR * Math.cos(angle)
    const y1 = cy + outerR * Math.sin(angle)
    angle += slice
    const x2 = cx + outerR * Math.cos(angle)
    const y2 = cy + outerR * Math.sin(angle)
    const large = slice > Math.PI ? 1 : 0
    const ix1 = cx + innerR * Math.cos(angle)
    const iy1 = cy + innerR * Math.sin(angle)
    const ix2 = cx + innerR * Math.cos(angle - slice)
    const iy2 = cy + innerR * Math.sin(angle - slice)
    const isTopRisk = item.key === maxItem.key && items.length > 1
    const fill = isTopRisk ? C.warn : GREEN_PALETTE[i % GREEN_PALETTE.length]

    arcs += `<path d="M ${x1} ${y1} A ${outerR} ${outerR} 0 ${large} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerR} ${innerR} 0 ${large} 0 ${ix2} ${iy2} Z" fill="${fill}" opacity="${isTopRisk ? 0.92 : 0.78}" stroke="rgba(2,8,5,0.6)" stroke-width="1" />`

    const ly = 28 + i * 18
    const displayLabel = item.label || item.key
    legend += `
      <rect x="18" y="${ly - 9}" width="10" height="10" fill="${fill}" opacity="0.85" />
      <text x="34" y="${ly}" fill="${C.text}" font-size="9">${escapeText(displayLabel)}</text>
      <text x="${width - 18}" y="${ly}" fill="${C.green}" font-size="9" text-anchor="end">${item.value}</text>
    `
  })

  arcs += `
    <text x="${cx}" y="${cy - 4}" fill="${C.green}" font-size="16" text-anchor="middle">${total}</text>
    <text x="${cx}" y="${cy + 12}" fill="${C.text}" font-size="8" text-anchor="middle">合计</text>
    ${legend}
  `

  mountSvg(container, width, height, arcs)
}

export function renderImpactBarChart(container, items) {
  if (!container) return
  const width = 680
  const rowH = 30
  const pad = { t: 14, r: 72, b: 14, l: 260 }
  const height = pad.t + pad.b + items.length * rowH

  if (!items.length) {
    mountSvg(container, width, 120, `<text x="${width / 2}" y="60" fill="${C.text}" font-size="11" text-anchor="middle">暂无数据</text>`)
    return
  }

  const max = Math.max(...items.map((d) => d.value), 1)
  const plotW = width - pad.l - pad.r
  let content = ''

  items.forEach((item, i) => {
    const y = pad.t + i * rowH
    const barW = (item.value / max) * plotW
    const isTop = i === 0
    const isCritical = (item.casualties || 0) >= 500
    const barColor = isTop || isCritical ? C.warn : C.green
    const trackOpacity = isTop ? 0.28 : 0.18
    content += `
      <text x="${pad.l - 10}" y="${y + 17}" fill="${C.text}" font-size="9" text-anchor="end">${escapeText(truncateLabel(item.label, 22))}</text>
      <rect x="${pad.l}" y="${y + 6}" width="${plotW}" height="14" fill="${C.greenDim}" opacity="${trackOpacity}" />
      <rect x="${pad.l}" y="${y + 6}" width="${barW}" height="14" fill="${barColor}" opacity="${isTop ? 0.92 : 0.78}" />
      <text x="${pad.l + plotW + 8}" y="${y + 17}" fill="${C.green}" font-size="8" opacity="0.85">${formatCompact(item.value)}</text>
    `
  })

  mountSvg(container, width, height, content)
}

export function renderMapLegend(container) {
  if (!container) return
  const tiers = [
    { label: '普通', color: C.green },
    { label: '高影响', color: C.warn },
    { label: '严重', color: C.danger },
  ]
  container.innerHTML = tiers
    .map(
      (tier) => `
    <span class="intel-map-legend__item">
      <i style="background:${tier.color}"></i>
      ${tier.label}
    </span>
  `,
    )
    .join('')
}

// Keep export for any legacy reference — palette is now tier-based
export const DISASTER_TYPE_COLORS = MAP_TIER
