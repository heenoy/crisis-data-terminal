import { supabase } from './supabase.js'
import { normalizeUsername, roleFromAppMetadata, usernameToInternalEmail } from './authIdentity.js'

const LEGACY_SESSION_KEY = 'crisis_user'

let currentUser = null
let authSubscription = null
let suppressAuthEvents = false
const listeners = new Set()

function clearLegacyAuthStorage() {
  sessionStorage.removeItem(LEGACY_SESSION_KEY)
  localStorage.removeItem(LEGACY_SESSION_KEY)
}

function emit(user) {
  currentUser = user
  listeners.forEach((fn) => fn(user))
}

function toAppUser(authUser) {
  if (!authUser?.id) return null

  const username = String(authUser.user_metadata?.username || '').trim().toLowerCase()
  const displayName = String(authUser.user_metadata?.display_name || username).trim()

  return {
    id: authUser.id,
    username,
    display_name: displayName || username,
    role: roleFromAppMetadata(authUser.app_metadata),
  }
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

export async function initAuth() {
  // Remove the legacy identity cache. Supabase Auth owns session persistence now.
  clearLegacyAuthStorage()

  if (!authSubscription) {
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (suppressAuthEvents) return
      emit(toAppUser(session?.user))
    })
    authSubscription = data.subscription
  }

  const { data, error } = await supabase.auth.getSession()
  if (error) {
    emit(null)
    return { user: null, error }
  }

  const user = toAppUser(data.session?.user)
  emit(user)
  return { user, error: null }
}

export async function refreshSessionUser() {
  const { data, error } = await supabase.auth.getUser()
  const user = error ? null : toAppUser(data.user)
  emit(user)
  return { user, stale: !user, error: error || null }
}

export async function signIn(username, password) {
  let email
  try {
    email = usernameToInternalEmail(username)
  } catch (error) {
    return { data: null, error }
  }

  const { data, error } = await supabase.auth.signInWithPassword({ email, password })

  if (error) {
    return { data: null, error: { message: '用户名或密码错误。' } }
  }

  const user = toAppUser(data.user)
  emit(user)
  return { data: user, error: null }
}

export async function signUp(username, password, displayName) {
  let normalizedUsername
  let email
  try {
    normalizedUsername = normalizeUsername(username)
    email = usernameToInternalEmail(normalizedUsername)
  } catch (error) {
    return { data: null, error }
  }

  suppressAuthEvents = true
  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          username: normalizedUsername,
          display_name: String(displayName || normalizedUsername).trim() || normalizedUsername,
        },
      },
    })

    if (error) {
      const message = /already|registered|exists/i.test(error.message || '')
        ? '用户名已存在，请更换后重试。'
        : '注册失败，请稍后重试。'
      return { data: null, error: { message } }
    }

    // With email confirmation disabled, signUp creates a session. Registration in this
    // UI still returns to the login tab, so close that new session explicitly.
    if (data.session) await supabase.auth.signOut()
    emit(null)
    return { data: { user: data.user }, error: null }
  } finally {
    suppressAuthEvents = false
  }
}

export async function signOut() {
  clearLegacyAuthStorage()
  const { error } = await supabase.auth.signOut()
  if (error) return { error }
  emit(null)
  return { error: null }
}
