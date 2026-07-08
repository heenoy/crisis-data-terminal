import { formatStatNumber, statNumberOrZero } from './statFormat.js'

async function loadEcharts() {
  const mod = await import('echarts')
  return mod.default || mod
}

const COLORS = {
  green: '#39ff88',
  greenDim: '#124a2a',
  greenLine: 'rgba(57, 255, 136, 0.28)',
  greenLineActive: 'rgba(57, 255, 136, 0.72)',
  orange: '#ffb347',
  red: '#ff5555',
  text: '#d8ffe0',
  dim: 'rgba(95, 143, 112, 0.72)',
}

const CATEGORY_STYLES = {
  country: {
    color: COLORS.green,
    shadowColor: 'rgba(57, 255, 136, 0.28)',
  },
  type: {
    color: COLORS.orange,
    shadowColor: 'rgba(255, 179, 71, 0.24)',
  },
  severity: {
    color: COLORS.red,
    shadowColor: 'rgba(255, 85, 85, 0.22)',
  },
}

function layoutNodes(nodes) {
  const countries = nodes.filter((node) => node.kind === 'country')
  const types = nodes.filter((node) => node.kind === 'type')
  const severities = nodes.filter((node) => node.kind === 'severity')

  countries.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(countries.length, 1)
    node.x = Math.cos(angle) * 420
    node.y = Math.sin(angle) * 250
  })

  types.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(types.length, 1)
    node.x = Math.cos(angle) * 175
    node.y = Math.sin(angle) * 105
  })

  severities.forEach((node, index) => {
    node.x = 270
    node.y = (index - (severities.length - 1) / 2) * 92
  })

  return nodes
}

function nodeStyle(node, activeIds = null) {
  const style = CATEGORY_STYLES[node.kind] || CATEGORY_STYLES.type
  const dimmed = activeIds && !activeIds.has(node.id)
  return {
    color: style.color,
    opacity: dimmed ? 0.16 : 1,
    borderColor: dimmed ? 'rgba(57, 255, 136, 0.15)' : 'rgba(216, 255, 224, 0.82)',
    borderWidth: node.kind === 'country' ? 2 : 1,
    shadowBlur: dimmed ? 0 : node.kind === 'country' ? 8 : 5,
    shadowColor: style.shadowColor,
  }
}

function linkStyle(link, activeIds = null) {
  const connected = activeIds && activeIds.has(link.source) && activeIds.has(link.target)
  const dimmed = activeIds && !connected
  return {
    ...(link.lineStyle || {}),
    color: dimmed ? 'rgba(57, 255, 136, 0.04)' : COLORS.greenLine,
    opacity: dimmed ? 0.08 : 0.72,
    curveness: 0.08,
    shadowBlur: connected ? 3 : 0,
    shadowColor: COLORS.greenLineActive,
  }
}

function decorateGraph(network, activeIds = null) {
  return {
    nodes: layoutNodes((network.nodes || []).map((node) => ({
      ...node,
      draggable: true,
      itemStyle: nodeStyle(node, activeIds),
      label: {
        show: node.kind !== 'severity' || statNumberOrZero(node.value) > 200,
      },
    }))),
    links: (network.links || []).map((link) => ({
      ...link,
      lineStyle: linkStyle(link, activeIds),
    })),
  }
}

function buildAdjacency(links) {
  const adjacency = new Map()
  ;(links || []).forEach((link) => {
    if (!adjacency.has(link.source)) adjacency.set(link.source, new Set())
    if (!adjacency.has(link.target)) adjacency.set(link.target, new Set())
    adjacency.get(link.source).add(link.target)
    adjacency.get(link.target).add(link.source)
  })
  return adjacency
}

function relatedIds(nodeId, adjacency) {
  const ids = new Set([nodeId])
  ;(adjacency.get(nodeId) || []).forEach((id) => {
    ids.add(id)
    ;(adjacency.get(id) || []).forEach((nextId) => ids.add(nextId))
  })
  return ids
}

function tooltipFormatter(params) {
  const node = params.data || {}
  if (params.dataType !== 'node') {
    return [
      `事件数量：${formatStatNumber(node.value)}`,
    ].join('<br/>')
  }

  if (node.kind === 'country') {
    return [
      `<strong style="color:${COLORS.green}">${node.name}</strong>`,
      `国家：${node.name}`,
      `事件数量：${formatStatNumber(node.value)}`,
      `灾害类型：${node.metrics?.disasterTypes || '--'}`,
      `风险等级：${node.metrics?.severities || '--'}`,
    ].join('<br/>')
  }

  if (node.kind === 'type') {
    return [
      `<strong style="color:${COLORS.orange}">${node.name}</strong>`,
      `国家：--`,
      `事件数量：${formatStatNumber(node.value)}`,
      `灾害类型：${node.name}`,
      `风险等级：${node.metrics?.severities || '--'}`,
    ].join('<br/>')
  }

  return [
    `<strong style="color:${COLORS.red}">${node.name}</strong>`,
    `国家：--`,
    `事件数量：${formatStatNumber(node.value)}`,
    `灾害类型：--`,
    `风险等级：${node.name}`,
  ].join('<br/>')
}

export async function renderDisasterRelationNetwork(container, network) {
  if (!container) return () => {}

  if (!network?.nodes?.length || !network?.links?.length) {
    container.innerHTML = '<p class="intel-relation-empty">暂无灾害关系数据</p>'
    return () => {}
  }

  const echarts = await loadEcharts()
  const chart = echarts.init(container, null, { renderer: 'canvas' })
  const adjacency = buildAdjacency(network.links)
  const decorated = decorateGraph(network)

  chart.setOption({
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 700,
    animationEasing: 'cubicOut',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(2, 8, 5, 0.94)',
      borderColor: 'rgba(57, 255, 136, 0.36)',
      textStyle: {
        color: COLORS.text,
        fontSize: 12,
      },
      formatter: tooltipFormatter,
    },
    legend: {
      show: true,
      bottom: 0,
      left: 8,
      icon: 'circle',
      textStyle: {
        color: COLORS.dim,
        fontSize: 11,
      },
      data: ['国家', '灾害类型', '风险等级'],
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: decorated.nodes,
        links: decorated.links,
        categories: network.categories,
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 6],
        label: {
          show: true,
          color: COLORS.text,
          fontSize: 11,
          formatter: ({ data }) => data.name,
        },
        edgeLabel: {
          show: false,
        },
        emphasis: {
          focus: 'adjacency',
          itemStyle: {
            shadowBlur: 10,
          },
          lineStyle: {
            color: COLORS.greenLineActive,
            opacity: 1,
          },
        },
        force: {
          repulsion: 120,
          gravity: 0.025,
          friction: 0.82,
          edgeLength: [84, 150],
          layoutAnimation: true,
        },
      },
    ],
  })

  let activeId = null
  const restore = () => {
    activeId = null
    const next = decorateGraph(network)
    chart.setOption({ series: [{ data: next.nodes, links: next.links }] })
  }

  chart.on('click', (params) => {
    if (params.dataType !== 'node') return
    activeId = params.data.id
    const activeIds = relatedIds(activeId, adjacency)
    const next = decorateGraph(network, activeIds)
    chart.setOption({ series: [{ data: next.nodes, links: next.links }] })
  })

  chart.getZr().on('click', (event) => {
    if (!event.target && activeId) restore()
  })

  const settleTimer = window.setTimeout(() => {
    chart.setOption({
      series: [
        {
          force: {
            layoutAnimation: false,
          },
        },
      ],
    })
  }, 1300)

  const onResize = () => chart.resize()
  window.addEventListener('resize', onResize)

  return () => {
    window.clearTimeout(settleTimer)
    window.removeEventListener('resize', onResize)
    chart.dispose()
  }
}
