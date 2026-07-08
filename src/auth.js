import { supabase } from './supabase.js'

export const SESSION_KEY = 'crisis_user'

let currentUser = null
const listeners = new Set()

function emit(user) {
  currentUser = user
  listeners.forEach((fn) => fn(user))
}

function toPublicUser(row) {
  if (!row) return null
  const { password: _password, ...user } = row
  return user
}

function persistUser(row) {
  const user = toPublicUser(row)
  if (user) {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(user))
  } else {
    sessionStorage.removeItem(SESSION_KEY)
  }
  emit(user)
}

export function getCurrentUser() {
  return currentUser
}

export function isLoggedIn() {
  return !!currentUser
}

export function subscribeAuth(fn) {
  listeners.add(fn)
  fn(currentUser)
  return () => listeners.delete(fn)
}

export function initAuth() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    const user = raw ? JSON.parse(raw) : null
    emit(user && user.id ? user : null)
  } catch (err) {
    console.warn('[Crisis Data Terminal] session restore failed:', err)
    sessionStorage.removeItem(SESSION_KEY)
    emit(null)
  }
}

export async function refreshSessionUser() {
  if (!currentUser?.username && !currentUser?.id) {
    return { user: null, stale: true }
  }

  let query = supabase
    .from('app_users')
    .select('id, username, display_name, role, created_at')

  if (currentUser.username) {
    query = query.eq('username', currentUser.username)
  } else {
    query = query.eq('id', currentUser.id)
  }

  const { data, error } = await query.maybeSingle()

  if (error || !data?.id) {
    signOut()
    return { user: null, stale: true }
  }

  persistUser(data)
  return { user: toPublicUser(data), stale: false }
}

export async function signIn(username, password) {
  const { data, error } = await supabase
    .from('app_users')
    .select('id, username, display_name, role, created_at, password')
    .eq('username', username)
    .eq('password', password)
    .maybeSingle()

  if (error) {
    return { error }
  }

  if (!data) {
    return { error: { message: '用户名或密码错误' } }
  }

  persistUser(data)
  return { data: toPublicUser(data) }
}

export async function signUp(username, password, displayName) {
  const { data: existing, error: lookupError } = await supabase
    .from('app_users')
    .select('id')
    .eq('username', username)
    .maybeSingle()

  if (lookupError) {
    return { error: lookupError }
  }

  if (existing) {
    return { error: { message: '用户名已存在，请更换后重试。' } }
  }

  const { data, error } = await supabase
    .from('app_users')
    .insert({
      username,
      password,
      display_name: displayName,
      role: 'operator',
    })
    .select('id, username, display_name, role, created_at')
    .single()

  if (error) {
    return { error }
  }

  return { data }
}

export function signOut() {
  sessionStorage.removeItem(SESSION_KEY)
  emit(null)
}
