function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function requestAppFullscreen() {
  const el = document.documentElement
  try {
    if (el.requestFullscreen) {
      await el.requestFullscreen()
    } else if (el.webkitRequestFullscreen) {
      el.webkitRequestFullscreen()
    }
  } catch {
    // unsupported or denied — continue silently
  }
}

export async function runLaunchSequence() {
  const overlay = document.getElementById('launch-overlay')
  const wakeOverlay = document.getElementById('wake-overlay')
  if (!overlay) return

  await new Promise((resolve) => {
    const onClick = async () => {
      overlay.removeEventListener('click', onClick)
      await requestAppFullscreen()
      if (wakeOverlay) wakeOverlay.hidden = false
      overlay.classList.add('launch-overlay--exiting')
      await delay(500)
      overlay.remove()
      resolve()
    }
    overlay.addEventListener('click', onClick)
  })
}
