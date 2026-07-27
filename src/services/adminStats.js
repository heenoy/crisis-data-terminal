import { supabase } from '../supabase.js'
import { countDisasterEvents } from '../disasterEvents.js'

export async function fetchAdminDashboardStats() {
  const [disasterResult, userResult] = await Promise.all([
    countDisasterEvents(),
    supabase.from('app_users').select('id', { count: 'exact', head: true }),
  ])

  const error = disasterResult.error || userResult.error || null

  return {
    disasterCount: disasterResult.count ?? 0,
    userCount: userResult.count ?? 0,
    databaseStatus: error ? 'UNAVAILABLE' : 'CONNECTED',
    error,
  }
}
