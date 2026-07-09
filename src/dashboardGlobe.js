import * as THREE from 'three'

let cleanupCurrentGlobe = null

const DOTS = [
  { lat: 58, lon: 88, size: 0.014, opacity: 0.95 },
  { lat: 34, lon: 114, size: 0.012, opacity: 0.9 },
  { lat: 23, lon: 78, size: 0.01, opacity: 0.76 },
  { lat: 39, lon: -98, size: 0.011, opacity: 0.82 },
  { lat: -15, lon: -47, size: 0.009, opacity: 0.68 },
  { lat: 51, lon: 10, size: 0.008, opacity: 0.66 },
  { lat: -26, lon: 134, size: 0.01, opacity: 0.7 },
  { lat: 0, lon: 32, size: 0.008, opacity: 0.62 },
  { lat: 36, lon: 138, size: 0.009, opacity: 0.74 },
  { lat: -34, lon: 18, size: 0.008, opacity: 0.64 },
]

function toSpherePoint(lat, lon, radius = 1) {
  const phi = ((90 - lat) * Math.PI) / 180
  const theta = (lon * Math.PI) / 180
  return new THREE.Vector3(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  )
}

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose?.()
    if (Array.isArray(child.material)) {
      child.material.forEach((material) => material.dispose?.())
    } else {
      child.material?.dispose?.()
    }
  })
}

function createLine(points, opacity, widthBoost = 1) {
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({
      color: 0x00ff41,
      transparent: true,
      opacity,
      linewidth: widthBoost,
    }),
  )
}

function createGlobeGroup() {
  const group = new THREE.Group()

  group.add(
    new THREE.Mesh(
      new THREE.SphereGeometry(1, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x000000 }),
    ),
  )

  for (let lon = 0; lon < 360; lon += 20) {
    const points = []
    for (let lat = -90; lat <= 90; lat += 3) {
      points.push(toSpherePoint(lat, lon, 1.002))
    }
    group.add(createLine(points, 0.25))
  }

  for (let lat = -80; lat <= 80; lat += 20) {
    const points = []
    for (let lon = 0; lon <= 360; lon += 3) {
      points.push(toSpherePoint(lat, lon, 1.003))
    }
    group.add(createLine(points, lat === 0 ? 0.48 : 0.2))
  }

  ;[66.5, -66.5].forEach((lat) => {
    const points = []
    for (let lon = 0; lon <= 360; lon += 3) {
      points.push(toSpherePoint(lat, lon, 1.004))
    }
    group.add(createLine(points, 0.34))
  })

  ;[
    { radius: 1.025, opacity: 0.045 },
    { radius: 1.055, opacity: 0.05 },
    { radius: 1.095, opacity: 0.025 },
  ].forEach(({ radius, opacity }) => {
    group.add(
      new THREE.Mesh(
        new THREE.SphereGeometry(radius, 64, 64),
        new THREE.MeshBasicMaterial({
          color: 0x00ff41,
          transparent: true,
          opacity,
          side: THREE.BackSide,
        }),
      ),
    )
  })

  const dotGroup = new THREE.Group()
  DOTS.forEach((dot, index) => {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(dot.size, 10, 10),
      new THREE.MeshBasicMaterial({
        color: index < 3 ? 0x39ff88 : 0x00dd55,
        transparent: true,
        opacity: dot.opacity,
      }),
    )
    marker.position.copy(toSpherePoint(dot.lat, dot.lon, 1.028))
    dotGroup.add(marker)

    if (index < 3) {
      const pulse = new THREE.Mesh(
        new THREE.SphereGeometry(dot.size * 2.25, 12, 12),
        new THREE.MeshBasicMaterial({
          color: 0x39ff88,
          transparent: true,
          opacity: 0.12,
          wireframe: true,
        }),
      )
      pulse.position.copy(marker.position)
      pulse.userData.pulse = true
      pulse.userData.baseOpacity = 0.12
      dotGroup.add(pulse)
    }
  })
  group.add(dotGroup)
  group.userData.dotGroup = dotGroup

  return group
}

export function destroyDashboardGlobe() {
  cleanupCurrentGlobe?.()
  cleanupCurrentGlobe = null
}

export function initDashboardGlobe(container) {
  if (!container) return

  destroyDashboardGlobe()
  container.innerHTML = ''

  const rect = container.getBoundingClientRect()
  const width = Math.max(320, Math.floor(rect.width || container.clientWidth || 640))
  const height = Math.max(320, Math.floor(rect.height || container.clientHeight || 520))

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6))
  renderer.setSize(width, height)
  renderer.setClearColor(0x000000, 0)
  renderer.domElement.className = 'situation-home-globe-canvas'
  renderer.domElement.style.cursor = 'grab'
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 1000)
  camera.position.set(0, 0, 3)

  const globeGroup = createGlobeGroup()
  scene.add(globeGroup)

  let rafId = null
  let active = true
  let autoRotate = true
  let rotationX = 0.1
  let rotationY = -0.32
  let dragging = false
  let prevX = 0
  let prevY = 0
  let resumeTimer = null

  function render() {
    if (!active) return
    rafId = requestAnimationFrame(render)
    if (autoRotate) rotationY += 0.0026
    globeGroup.rotation.set(rotationX, rotationY, 0)

    const t = Date.now() * 0.002
    globeGroup.userData.dotGroup?.children.forEach((child) => {
      if (child.userData.pulse) {
        child.material.opacity = child.userData.baseOpacity * (0.6 + 0.4 * Math.sin(t * 2))
      }
    })

    renderer.render(scene, camera)
  }

  function resize() {
    if (!container.isConnected) return
    const nextRect = container.getBoundingClientRect()
    const nextWidth = Math.max(320, Math.floor(nextRect.width || container.clientWidth || width))
    const nextHeight = Math.max(320, Math.floor(nextRect.height || container.clientHeight || height))
    renderer.setSize(nextWidth, nextHeight)
    camera.aspect = nextWidth / nextHeight
    camera.updateProjectionMatrix()
  }

  function handlePointerDown(event) {
    dragging = true
    autoRotate = false
    prevX = event.clientX
    prevY = event.clientY
    renderer.domElement.style.cursor = 'grabbing'
    if (resumeTimer) window.clearTimeout(resumeTimer)
  }

  function handlePointerMove(event) {
    if (!dragging) return
    rotationY += (event.clientX - prevX) * 0.004
    rotationX += (event.clientY - prevY) * 0.004
    rotationX = Math.max(-1.05, Math.min(1.05, rotationX))
    prevX = event.clientX
    prevY = event.clientY
  }

  function handlePointerUp() {
    if (!dragging) return
    dragging = false
    renderer.domElement.style.cursor = 'grab'
    resumeTimer = window.setTimeout(() => {
      autoRotate = true
    }, 1800)
  }

  const observer = new IntersectionObserver(
    (entries) => {
      active = entries[0]?.isIntersecting ?? true
      if (active && rafId == null) render()
    },
    { threshold: 0.05 },
  )

  window.addEventListener('resize', resize)
  renderer.domElement.addEventListener('pointerdown', handlePointerDown)
  window.addEventListener('pointermove', handlePointerMove)
  window.addEventListener('pointerup', handlePointerUp)
  observer.observe(container)
  render()

  cleanupCurrentGlobe = () => {
    active = false
    dragging = false
    if (resumeTimer) window.clearTimeout(resumeTimer)
    if (rafId != null) cancelAnimationFrame(rafId)
    rafId = null
    observer.disconnect()
    window.removeEventListener('resize', resize)
    renderer.domElement.removeEventListener('pointerdown', handlePointerDown)
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', handlePointerUp)
    disposeObject(scene)
    renderer.dispose()
    renderer.domElement.remove()
  }
}
