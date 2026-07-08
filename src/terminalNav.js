export function renderBackToMainMenu() {
  return `
    <div class="terminal-back-bar">
      <button type="button" class="terminal-back-bar__btn" data-route="start" aria-label="返回主菜单">
        ← 返回主菜单
      </button>
    </div>
  `
}

export function renderBackToDashboard() {
  return `
    <div class="terminal-back-bar">
      <button type="button" class="terminal-back-bar__btn" data-route="dashboard" aria-label="返回灾害事件总览">
        ← 返回灾害事件总览
      </button>
    </div>
  `
}

export function renderBackToStart() {
  return `
    <div class="terminal-back-bar">
      <button type="button" class="terminal-back-bar__btn" data-route="start" aria-label="返回终端入口">
        ← 返回终端入口
      </button>
    </div>
  `
}

export function renderDashboardQuickNav() {
  return `
    <nav class="terminal-quick-nav" aria-label="模块入口">
      <button type="button" data-route="query">→ 灾害事件查询</button>
      <button type="button" data-route="analytics">→ 数据分析中心</button>
    </nav>
  `
}

export function bindTerminalNavigation({ onNavigate, root = document }) {
  root.querySelectorAll(
    '.terminal-back-bar [data-route], .terminal-quick-nav [data-route], .terminal-page-footer [data-route], .situation-dashboard [data-route]',
  ).forEach((button) => {
    button.addEventListener('click', () => onNavigate?.(button.dataset.route))
  })
}

export function renderTerminalPageFooter({ backRoute = 'dashboard' } = {}) {
  const label = backRoute === 'start' ? '返回终端入口' : '返回灾害事件总览'
  return `
    <footer class="terminal-page-footer">
      <button type="button" class="terminal-page-footer__btn" data-route="${backRoute}">
        [ ${label} / RETURN ]
      </button>
    </footer>
  `
}
