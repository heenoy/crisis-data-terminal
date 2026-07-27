import { bindDisasterDashboard, renderDisasterDashboard } from '../../disasterEventsPage.js'

export function renderAdminDisasterManage(user) {
  return renderDisasterDashboard({ user, mode: 'console' })
}

export function initAdminDisasterManage({ user, onNavigate }) {
  bindDisasterDashboard({ user, onNavigate, mode: 'console' })
}
