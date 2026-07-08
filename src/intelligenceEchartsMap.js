import { labelDisasterType, labelCountry } from './disasterEvents.js'
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

function ensureWorldMap(echarts) {
  if (!worldReady) {
    worldReady = fetch(`${import.meta.env.BASE_URL}world.geo.json`)
      .then((res) => {
        if (!res.ok) throw new Error('世界地图数据加载失败')
        return res.json()
      })
      .then((geo) => {
        echarts.registerMap('world', geo)
      })
  }
  return worldReady
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

export async function renderEchartsWorldMap(container, points) {
  if (!container) return () => {}

  const echarts = await loadEcharts()
  await ensureWorldMap(echarts)

  const prev = echarts.getInstanceByDom(container)
  if (prev) prev.dispose()

  const chart = echarts.init(container, null, { renderer: 'canvas' })

  const scatterData = (points || [])
    .filter((p) => p.lat != null && p.lng != null)
    .map((point) => {
      const tier = mapPointTier(point)
      const impact = statNumberOrZero(point.casualties) * 1000 + statNumberOrZero(point.affected_population)
      return {
        name: point.title,
        value: [point.lng, point.lat, impact],
        tier,
        event: point,
        itemStyle: {
          color: TIER_COLOR[tier],
          shadowBlur: tier === 'normal' ? 6 : 10,
          shadowColor: `${TIER_COLOR[tier]}88`,
        },
      }
    })

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
          `<span style="color:${C.green};font-weight:600;">${event.title}</span>`,
          `灾害类型：${labelDisasterType(event.disaster_type)}`,
          `国家/地区：${labelCountry(event.country)}`,
          `死亡人数：${formatStatNumber(event.casualties)}`,
          `受影响人数：${formatStatNumber(event.affected_population)}`,
          `地理位置：${event.lat.toFixed(2)}°，${event.lng.toFixed(2)}°`,
        ].join('<br/>')
      },
    },
    series: [
      {
        type: 'scatter',
        coordinateSystem: 'geo',
        data: scatterData,
        symbolSize: (val) => symbolSize(val),
        emphasis: {
          scale: 1.25,
        },
      },
    ],
  })

  const onResize = () => chart.resize()
  window.addEventListener('resize', onResize)

  return () => {
    window.removeEventListener('resize', onResize)
    chart.dispose()
  }
}
