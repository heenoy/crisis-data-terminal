let flickerTimer = null

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function spawnNoisePixels(count) {
  for (let i = 0; i < count; i++) {
    const dot = document.createElement('div')
    dot.className = 'screen-noise-pixel'
    dot.style.top = `${randomInt(0, window.innerHeight - 2)}px`
    dot.style.left = `${randomInt(0, window.innerWidth - 2)}px`
    document.body.appendChild(dot)
    window.setTimeout(() => dot.remove(), 100)
  }
}

async function triggerLightScreenFlicker() {
  const body = document.body
  const flickers = randomInt(2, 3)

  body.classList.add('screen-micro-flicker')

  for (let i = 0; i < flickers; i++) {
    body.style.opacity = '0.85'
    await new Promise((r) => window.setTimeout(r, randomInt(50, 80)))
    body.style.opacity = '1'
    await new Promise((r) => window.setTimeout(r, randomInt(50, 80)))
  }

  body.style.opacity = ''
  body.classList.remove('screen-micro-flicker')
  spawnNoisePixels(randomInt(3, 5))
}

function scheduleScreenFlicker() {
  if (flickerTimer) clearTimeout(flickerTimer)
  flickerTimer = window.setTimeout(async () => {
    await triggerLightScreenFlicker()
    scheduleScreenFlicker()
  }, randomInt(15000, 25000))
}

export function setRoundProgress(current, total) {
  const bar = document.getElementById('screen-bar-bl')
  if (!bar) return
  bar.textContent = `[ROUND ${pad2(current)}/${total}]`
}

export function setDecisionType(type) {
  const bar = document.getElementById('screen-bar-br')
  if (!bar) return
  bar.textContent = `[${type}]`
}

export function initVisualLayer() {
  document.documentElement.style.setProperty(
    '--glitch-border-delay',
    `${(Math.random() * 8).toFixed(2)}s`
  )
  scheduleScreenFlicker()
}

export function destroyVisualLayer() {
  if (flickerTimer) clearTimeout(flickerTimer)
  flickerTimer = null
}
