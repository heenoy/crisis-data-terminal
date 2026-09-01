export const ROUTES = Object.freeze({
  START: 'start',
  AUTH: 'auth',
  USER_OVERVIEW: 'user/overview',
  USER_SEARCH: 'user/search',
  USER_ANALYSIS: 'user/analysis',
  USER_IMPACT_ANALYSIS: 'user/impact-analysis',
  USER_AI_INQUIRY: 'user/ai-inquiry',
  ADMIN_DASHBOARD: 'admin/dashboard',
  ADMIN_DISASTERS: 'admin/disasters',
  ADMIN_USERS: 'admin/users',
  ADMIN_SYSTEM: 'admin/system',
  ADMIN_MODELS: 'admin/models',
})

const ROUTE_ALIASES = Object.freeze({
  '': ROUTES.START,
  start: ROUTES.START,
  auth: ROUTES.AUTH,
  login: ROUTES.AUTH,
  register: ROUTES.AUTH,
  dashboard: ROUTES.USER_OVERVIEW,
  home: ROUTES.USER_OVERVIEW,
  query: ROUTES.USER_SEARCH,
  archive: ROUTES.USER_SEARCH,
  analytics: ROUTES.USER_ANALYSIS,
  analysis: ROUTES.USER_ANALYSIS,
  situation: ROUTES.USER_ANALYSIS,
  status: ROUTES.USER_ANALYSIS,
  knowledge: ROUTES.USER_AI_INQUIRY,
  docs: ROUTES.USER_AI_INQUIRY,
  documentation: ROUTES.USER_AI_INQUIRY,
  'user/overview': ROUTES.USER_OVERVIEW,
  'user/search': ROUTES.USER_SEARCH,
  'user/analysis': ROUTES.USER_ANALYSIS,
  'impact-analysis': ROUTES.USER_IMPACT_ANALYSIS,
  'user/impact-analysis': ROUTES.USER_IMPACT_ANALYSIS,
  'user/ai-inquiry': ROUTES.USER_AI_INQUIRY,
  'admin/dashboard': ROUTES.ADMIN_DASHBOARD,
  'admin/disasters': ROUTES.ADMIN_DISASTERS,
  'admin/users': ROUTES.ADMIN_USERS,
  'admin/system': ROUTES.ADMIN_SYSTEM,
  'admin/models': ROUTES.ADMIN_MODELS,
})

export const PUBLIC_ROUTES = new Set([ROUTES.START, ROUTES.AUTH])
export const USER_ROUTES = new Set([
  ROUTES.USER_OVERVIEW,
  ROUTES.USER_SEARCH,
  ROUTES.USER_ANALYSIS,
  ROUTES.USER_IMPACT_ANALYSIS,
  ROUTES.USER_AI_INQUIRY,
])
export const ADMIN_ROUTES = new Set([
  ROUTES.ADMIN_DASHBOARD,
  ROUTES.ADMIN_DISASTERS,
  ROUTES.ADMIN_USERS,
  ROUTES.ADMIN_SYSTEM,
  ROUTES.ADMIN_MODELS,
])

export function normalizeRoute(route) {
  let key = String(route || '').trim().toLowerCase()
  key = key.replace(/^#\/?/, '').replace(/^\//, '').replace(/\/+$/, '')
  return ROUTE_ALIASES[key] || ROUTES.START
}

export function isKnownRole(role) {
  return role === 'admin' || role === 'user'
}

export function defaultRouteForRole(role) {
  if (role === 'admin') return ROUTES.ADMIN_DASHBOARD
  if (role === 'user') return ROUTES.USER_OVERVIEW
  return ROUTES.AUTH
}

export function authorizeRoute(route, user) {
  const normalized = normalizeRoute(route)
  const role = user?.role

  if (normalized === ROUTES.AUTH && user) {
    return {
      route: defaultRouteForRole(role),
      allowed: isKnownRole(role),
      reason: isKnownRole(role) ? 'already-authenticated' : 'invalid-role',
    }
  }

  if (PUBLIC_ROUTES.has(normalized)) {
    return { route: normalized, allowed: true, reason: null }
  }

  if (!user) {
    return { route: ROUTES.AUTH, allowed: false, reason: 'authentication-required' }
  }

  if (!isKnownRole(role)) {
    return { route: ROUTES.AUTH, allowed: false, reason: 'invalid-role' }
  }

  if (ADMIN_ROUTES.has(normalized) && role !== 'admin') {
    return { route: ROUTES.USER_OVERVIEW, allowed: false, reason: 'admin-required' }
  }

  if (USER_ROUTES.has(normalized) || ADMIN_ROUTES.has(normalized)) {
    return { route: normalized, allowed: true, reason: null }
  }

  return { route: ROUTES.START, allowed: true, reason: null }
}
