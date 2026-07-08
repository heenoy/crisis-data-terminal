let audioContext = null
let audioReady = false
let unlockAudio = null
let lastTypewriterAt = 0
let lastGlitchAt = 0

const TYPEWRITER_MIN_GAP = 30
const GLITCH_MIN_GAP = 200
const GLITCH_PLAY_CHANCE = 0.22
const GLITCH_VOLUME = 0.022

const TYPEWRITER_FREQ = 440
const TYPEWRITER_DURATION = 0.015
const TYPEWRITER_VOLUME = 0.03
const TYPEWRITER_SKIP_CHARS = new Set([' ', '。', '，', '？', '！', '：'])

export async function ensureAudioContext() {
  if (!audioContext) {
    audioContext = new AudioContext()
  }
  if (audioContext.state === 'suspended') {
    await audioContext.resume()
  }
  audioReady = audioContext.state === 'running'
  return audioReady
}

export function setupAudioUnlock() {
  if (unlockAudio) return

  unlockAudio = async () => {
    await ensureAudioContext()

    document.removeEventListener('pointerdown', unlockAudio)
    document.removeEventListener('keydown', unlockAudio)
    unlockAudio = null
  }

  document.addEventListener('pointerdown', unlockAudio)
  document.addEventListener('keydown', unlockAudio)
}

export function destroyAudio() {
  if (unlockAudio) {
    document.removeEventListener('pointerdown', unlockAudio)
    document.removeEventListener('keydown', unlockAudio)
    unlockAudio = null
  }
  if (audioContext) audioContext.close()
  audioContext = null
  audioReady = false
  lastTypewriterAt = 0
  lastGlitchAt = 0
}

export function playTypewriterClick(char) {
  if (char !== undefined && TYPEWRITER_SKIP_CHARS.has(char)) return
  if (!audioReady || !audioContext) return

  const now = performance.now()
  if (now - lastTypewriterAt < TYPEWRITER_MIN_GAP) return
  lastTypewriterAt = now

  const t = audioContext.currentTime
  const osc = audioContext.createOscillator()
  const gain = audioContext.createGain()

  osc.type = 'sine'
  osc.frequency.value = TYPEWRITER_FREQ
  osc.connect(gain)
  gain.connect(audioContext.destination)

  gain.gain.setValueAtTime(TYPEWRITER_VOLUME, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + TYPEWRITER_DURATION)

  osc.start(t)
  osc.stop(t + TYPEWRITER_DURATION)
}

export function playGlitchClick() {
  if (Math.random() > GLITCH_PLAY_CHANCE) return
  if (!audioReady || !audioContext) return

  const now = performance.now()
  if (now - lastGlitchAt < GLITCH_MIN_GAP) return
  lastGlitchAt = now

  const t = audioContext.currentTime
  const duration = 0.022
  const sampleRate = audioContext.sampleRate
  const bufferSize = Math.max(1, Math.floor(sampleRate * duration))
  const buffer = audioContext.createBuffer(1, bufferSize, sampleRate)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < bufferSize; i++) {
    data[i] = (Math.random() * 2 - 1) * (1 - i / bufferSize)
  }

  const source = audioContext.createBufferSource()
  source.buffer = buffer

  const filter = audioContext.createBiquadFilter()
  filter.type = 'bandpass'
  filter.frequency.value = 350 + Math.random() * 600
  filter.Q.value = 1.5

  const gain = audioContext.createGain()
  gain.gain.setValueAtTime(GLITCH_VOLUME, t)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(audioContext.destination)
  source.start(t)
  source.stop(t + duration)
}

function playGeigerTick(atTime) {
  const duration = 0.01
  const sampleRate = audioContext.sampleRate
  const bufferSize = Math.max(1, Math.floor(sampleRate * duration))
  const buffer = audioContext.createBuffer(1, bufferSize, sampleRate)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < bufferSize; i++) {
    data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.25))
  }

  const source = audioContext.createBufferSource()
  source.buffer = buffer

  const filter = audioContext.createBiquadFilter()
  filter.type = 'highpass'
  filter.frequency.value = 1800 + Math.random() * 1200
  filter.Q.value = 0.8

  const gain = audioContext.createGain()
  gain.gain.setValueAtTime(0.07, atTime)
  gain.gain.exponentialRampToValueAtTime(0.0001, atTime + duration)

  source.connect(filter)
  filter.connect(gain)
  gain.connect(audioContext.destination)
  source.start(atTime)
  source.stop(atTime + duration)
}

export async function playGeigerClick() {
  const ready = await ensureAudioContext()
  if (!ready) return

  const t = audioContext.currentTime
  const clicks = 5 + Math.floor(Math.random() * 4)
  let offset = 0.03

  for (let i = 0; i < clicks; i++) {
    playGeigerTick(t + offset)
    offset += 0.05 + Math.random() * 0.11
  }
}

export async function playBarFillTick() {
  const ready = await ensureAudioContext()
  if (!ready) return

  const t = audioContext.currentTime
  const osc = audioContext.createOscillator()
  const gain = audioContext.createGain()

  osc.type = 'square'
  osc.frequency.value = 110 + Math.random() * 30
  osc.connect(gain)
  gain.connect(audioContext.destination)

  gain.gain.setValueAtTime(0.04, t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.06)

  osc.start(t)
  osc.stop(t + 0.06)
}

export function playAnomalyWhiteNoise() {
  if (!audioReady || !audioContext) return

  const t = audioContext.currentTime
  const duration = 0.08
  const sampleRate = audioContext.sampleRate
  const bufferSize = Math.max(1, Math.floor(sampleRate * duration))
  const buffer = audioContext.createBuffer(1, bufferSize, sampleRate)
  const data = buffer.getChannelData(0)

  for (let i = 0; i < bufferSize; i++) {
    data[i] = Math.random() * 2 - 1
  }

  const source = audioContext.createBufferSource()
  source.buffer = buffer

  const gain = audioContext.createGain()
  gain.gain.setValueAtTime(0.035, t)
  gain.gain.exponentialRampToValueAtTime(0.0001, t + duration)

  source.connect(gain)
  gain.connect(audioContext.destination)
  source.start(t)
  source.stop(t + duration)
}
