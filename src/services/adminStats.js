import { countDisasterEvents } from '../disasterEvents.js'

export async function fetchAdminDashboardStats() {
  const disasterResult = await countDisasterEvents()
  const error = disasterResult.error || null

  return {
    disasterCount: disasterResult.count ?? 0,
    // Auth user counts require a trusted server-side Admin API and are not read from app_users.
    userCount: 'N/A',
    databaseStatus: error ? 'UNAVAILABLE' : 'CONNECTED',
    error,
  }
}
