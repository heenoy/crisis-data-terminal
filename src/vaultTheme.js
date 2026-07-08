const SHELL_ID = 'vault-terminal-stage'

function createPart(className, text = '') {
  const node = document.createElement('div')
  node.className = className
  if (text) node.textContent = text
  node.setAttribute('aria-hidden', 'true')
  return node
}

function installVaultTerminalShell() {
  const screen = document.getElementById('screen')
  if (!screen || document.getElementById(SHELL_ID)) return

  const stage = document.createElement('div')
  stage.id = SHELL_ID
  stage.className = 'vault-terminal-stage'

  const shell = document.createElement('div')
  shell.className = 'vault-tv-shell'

  const frame = document.createElement('div')
  frame.className = 'vault-tv-frame'

  const bezel = document.createElement('div')
  bezel.className = 'vault-tv-bezel'

  const hardware = document.createElement('div')
  hardware.className = 'vault-tv-hardware'
  hardware.append(
    createPart('vault-tv-status-light'),
    createPart('vault-tv-hardware-label', 'VAULT-0 TERMINAL UNIT'),
    createPart('vault-tv-hardware-slots'),
  )

  const parent = screen.parentNode
  parent.insertBefore(stage, screen)
  stage.appendChild(shell)
  shell.appendChild(frame)
  frame.appendChild(bezel)
  bezel.appendChild(screen)
  shell.appendChild(hardware)

  for (const corner of ['tl', 'tr', 'bl', 'br']) {
    shell.appendChild(createPart(`vault-tv-screw vault-tv-screw--${corner}`))
  }
}

installVaultTerminalShell()

