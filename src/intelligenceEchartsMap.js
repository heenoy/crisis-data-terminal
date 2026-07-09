import { labelCountry, labelDisasterType } from './disasterEvents.js'
import { formatStatNumber, statNumberOrZero } from './statFormat.js'

const C = {
  bg: '#020805',
  panel: '#06150d',
  green: '#39ff88',
  text: '#5f8f70',
  warn: '#ffb347',
  danger: '#ff5555',
}

const TIER_COLOR = {
  normal: C.green,
  high: C.warn,
  critical: C.danger,
}

let worldReady = null
let echartsModule = null

async function loadEcharts() {
  if (!echartsModule) {
    echartsModule = await import('echarts')
  }
  return echartsModule
}

async function fetchWorldGeoJson() {
  const base = import.meta.env.BASE_URL || '/'
  const urls = [
    `${base.endsWith('/') ? base : `${base}/`}world.geo.json`,
    '/world.geo.json',
  ]

  let lastError = null
  for (const url of urls) {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`world.geo.json HTTP ${res.status}`)
      return res.json()
    } catch (error) {
      lastError = error
    }
  }

  throw lastError || new Error('world.geo.json load failed')
}

async function ensureWorldMap(echarts) {
  const existingMap = typeof echarts.getMap === 'function' ? echarts.getMap('world') : null
  if (existingMap) return

  if (!worldReady) {
    worldReady = fetchWorldGeoJson()
      .then((geo) => {
        echarts.registerMap('world', geo)
      })
      .catch((error) => {
        worldReady = null
        throw error
      })
  }

  await worldReady

  if (typeof echarts.getMap === 'function' && !echarts.getMap('world')) {
    throw new Error('world map registration failed')
  }
}

function mapPointTier(point) {
  const casualties = Number(point.casualties) || 0
  const affected = Number(point.affected_population) || 0
  if (casualties >= 500 || affected >= 500000) return 'critical'
  if (casualties >= 20 || affected >= 20000) return 'high'
  return 'normal'
}

function symbolSize(value) {
  const impact = Number(value?.[2]) || 0
  return Math.min(20, Math.max(5, Math.log10(impact + 10) * 3.2))
}

function hasRenderableSize(container) {
  if (!container || !document.body.contains(container)) return false
  const rect = container.getBoundingClientRect()
  const style = window.getComputedStyle(container)
  return rect.width > 8 && rect.height > 8 && style.display !== 'none' && style.visibility !== 'hidden'
}

function waitForRenderableSize(container, isDisposed) {
  return new Promise((resolve) => {
    let attempts = 0
    const tick = () => {
      if (isDisposed()) {
        resolve(false)
        return
      }
      if (hasRenderableSize(container)) {
        resolve(true)
        return
      }
      attempts += 1
      if (attempts >= 60) {
        resolve(false)
        return
      }
      requestAnimationFrame(tick)
    }
    tick()
  })
}

function showMapError(container) {
  if (!container || !document.body.contains(container)) return
  container.innerHTML = '<p class="intel-map-error">&gt; 世界地图模块加载失败</p>'
}

function buildScatterData(points) {
  return (points || [])
    .filter((point) => Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lng)))
    .map((point) => {
      const tier = mapPointTier(point)
      const impact = statNumberOrZero(point.casualties) * 1000 + statNumberOrZero(point.affected_population)
      return {
        name: point.title || '--',
        value: [Number(point.lng), Number(point.lat), impact],
        tier,
        event: point,
        itemStyle: {
          color: TIER_COLOR[tier],
          shadowBlur: tier === 'normal' ? 6 : 10,
          shadowColor: `${TIER_COLOR[tier]}88`,
        },
      }
    })
}

export async function renderEchartsWorldMap(container, points) {
  let chart = null
  let disposed = false

  const cleanup = () => {
    disposed = true
    window.removeEventListener('resize', onResize)
    chart?.dispose?.()
    chart = null
  }

  function onResize() {
    if (disposed || !chart || !container || !document.body.contains(container)) return
    if (!hasRenderableSize(container)) return
    chart.resize()
  }

  try {
    if (!container) return cleanup
    container.innerHTML = ''

    const ready = await waitForRenderableSize(container, () => disposed)
    if (disposed) return cleanup
    if (!ready) {
      showMapError(container)
      return cleanup
    }

    const echarts = await loadEcharts()
    await ensureWorldMap(echarts)
    if (disposed) return cleanup

    const prev = echarts.getInstanceByDom(container)
    if (prev) prev.dispose()

    chart = echarts.init(container, null, { renderer: 'canvas' })
    chart.setOption({
      backgroundColor: C.bg,
      geo: {
        map: 'world',
        roam: 'scale',
        zoom: 1.12,
        center: [12, 18],
        scaleLimit: { min: 0.8, max: 4 },
        itemStyle: {
          areaColor: C.panel,
          borderColor: 'rgba(57, 255, 136, 0.14)',
          borderWidth: 0.7,
        },
        emphasis: {
          itemStyle: {
            areaColor: '#0a2218',
            borderColor: 'rgba(57, 255, 136, 0.28)',
          },
          label: { show: false },
        },
        label: { show: false },
      },
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(2, 8, 5, 0.96)',
        borderColor: 'rgba(57, 255, 136, 0.22)',
        borderWidth: 1,
        padding: [8, 10],
        textStyle: {
          color: C.text,
          fontSize: 12,
          lineHeight: 18,
        },
        extraCssText: 'box-shadow:0 0 14px rgba(0,0,0,0.55);',
        formatter(params) {
          const event = params.data?.event
          if (!event) return ''
          return [
            `<span style="color:${C.green};font-weight:600;">${event.title || '--'}</span>`,
            `灾害类型：${labelDisasterType(event.disaster_type)}`,
            `国家/地区：${labelCountry(event.country)}`,
            `死亡人数：${formatStatNumber(event.casualties)}`,
            `受影响人数：${formatStatNumber(event.affected_population)}`,
            `地理位置：${Number(event.lat).toFixed(2)}°, ${Number(event.lng).toFixed(2)}°`,
          ].join('<br/>')
        },
      },
      series: [
        {
          type: 'scatter',
          coordinateSystem: 'geo',
          data: buildScatterData(points),
          symbolSize: (val) => symbolSize(val),
          emphasis: {
            scale: 1.25,
          },
        },
      ],
    })

    requestAnimationFrame(onResize)
    window.addEventListener('resize', onResize)
  } catch (error) {
    console.error('[Analytics map] render failed:', error)
    cleanup()
    showMapError(container)
  }

  return cleanup
}
