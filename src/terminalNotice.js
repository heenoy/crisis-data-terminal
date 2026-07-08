let noticeTimer = null

function getNoticeEl() {
  let el = document.getElementById('terminal-notice')
  if (!el) {
    el = document.createElement('div')
    el.id = 'terminal-notice'
    el.setAttribute('role', 'status')
    el.hidden = true
    document.getElementById('screen-content')?.appendChild(el)
  }
  return el
}

export function showTerminalNotice(message, type = 'success', duration = 3200) {
  const el = getNoticeEl()
  const prefix = type === 'success' ? '[OK]' : '[ERROR]'
  el.className = `terminal-notice terminal-notice--${type}`
  el.textContent = `> ${prefix} ${message}`
  el.hidden = false

  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    el.hidden = true
    noticeTimer = null
  }, duration)
}

export function hideTerminalNotice() {
  const el = document.getElementById('terminal-notice')
  if (el) el.hidden = true
  if (noticeTimer) {
    clearTimeout(noticeTimer)
    noticeTimer = null
  }
}
