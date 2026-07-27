import { bindAdminPlaceholder, renderAdminPlaceholder } from './placeholder.js'

export function renderAdminSystemMonitor() {
  return renderAdminPlaceholder({
    kicker: 'ADMIN_PORTAL / SYSTEM MONITOR',
    title: '系统监控',
    description: '数据库连接、数据更新与 Live Feed 监控入口',
  })
}

export const initAdminSystemMonitor = bindAdminPlaceholder
