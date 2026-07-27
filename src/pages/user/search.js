import { bindDisasterDashboard, renderDisasterDashboard } from '../../disasterEventsPage.js'

export function renderUserSearch(user) {
  return renderDisasterDashboard({ user, mode: 'query' })
}

export function initUserSearch({ user, onNavigate }) {
  bindDisasterDashboard({ user, onNavigate, mode: 'query' })
}
