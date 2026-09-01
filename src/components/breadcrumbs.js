import { ROUTES } from '../router/routes.js'

const SUBPAGE_ROUTES = new Set([
  ROUTES.USER_OVERVIEW,
  ROUTES.USER_SEARCH,
  ROUTES.USER_ANALYSIS,
  ROUTES.USER_IMPACT_ANALYSIS,
  ROUTES.USER_AI_INQUIRY,
  ROUTES.ADMIN_DASHBOARD,
  ROUTES.ADMIN_DISASTERS,
  ROUTES.ADMIN_USERS,
  ROUTES.ADMIN_SYSTEM,
  ROUTES.ADMIN_MODELS,
])

const ROUTE_LABELS = {
  [ROUTES.USER_OVERVIEW]: '世界灾害总览',
  [ROUTES.USER_SEARCH]: '灾害事件查询',
  [ROUTES.USER_ANALYSIS]: '数据分析中心',
  [ROUTES.USER_IMPACT_ANALYSIS]: '灾害影响等级预测',
  [ROUTES.USER_AI_INQUIRY]: 'AI 灾害问询',
  [ROUTES.ADMIN_DASHBOARD]: '管理控制台',
  [ROUTES.ADMIN_DISASTERS]: '灾害管理',
  [ROUTES.ADMIN_USERS]: '用户管理',
  [ROUTES.ADMIN_SYSTEM]: '系统监控',
  [ROUTES.ADMIN_MODELS]: '模型档案',
}

export function renderBreadcrumbs(route) {
  if (!SUBPAGE_ROUTES.has(route)) return ''
  const isAdminSubpage = route.startsWith('admin/') && route !== ROUTES.ADMIN_DASHBOARD
  const adminParent = isAdminSubpage
    ? `<span class="terminal-breadcrumbs__separator" aria-hidden="true">/</span>
       <button type="button" class="terminal-breadcrumbs__link" data-breadcrumb-route="${ROUTES.ADMIN_DASHBOARD}" aria-label="返回管理控制台">管理控制台</button>`
    : ''
  return `<nav class="terminal-breadcrumbs terminal-home-nav" aria-label="页面导航">
    <button type="button" class="terminal-breadcrumbs__link terminal-home-nav__button" data-breadcrumb-route="${ROUTES.START}" aria-label="返回主菜单">
      <span aria-hidden="true">&lt;</span> 主菜单
    </button>
    ${adminParent}
    <span class="terminal-breadcrumbs__separator" aria-hidden="true">/</span>
    <span class="terminal-breadcrumbs__current" aria-current="page">${ROUTE_LABELS[route]}</span>
  </nav>`
}

export function mountBreadcrumbs({ root, route, onNavigate }) {
  activeObserver?.disconnect()
  activeObserver = null
  const markup = renderBreadcrumbs(route)
  if (!markup) return
  const ensureNavigation = () => {
    root.querySelectorAll('.terminal-back-bar, .terminal-page-footer').forEach((node) => node.remove())
    const shell = root.querySelector('.vault-console--subpage')
    if (!shell || shell.querySelector('.terminal-home-nav')) return
    shell.insertAdjacentHTML('afterbegin', markup)
    shell.querySelectorAll('[data-breadcrumb-route]').forEach((button) => button.addEventListener('click', (event) => {
      onNavigate?.(event.currentTarget.dataset.breadcrumbRoute)
    }))
  }
  ensureNavigation()
  activeObserver = new MutationObserver(() => queueMicrotask(ensureNavigation))
  activeObserver.observe(root, { childList: true, subtree: true })
}

let activeObserver = null
