export const USERNAME_MIN_LENGTH = 3
export const USERNAME_MAX_LENGTH = 24
export const INTERNAL_AUTH_DOMAIN = 'users.cytuna.cn'

const USERNAME_PATTERN = /^[a-z0-9_]+$/

export function normalizeUsername(value) {
  const username = String(value ?? '').trim().toLowerCase()

  if (username.length < USERNAME_MIN_LENGTH || username.length > USERNAME_MAX_LENGTH) {
    throw new Error('用户名须为 3–24 个字符。')
  }

  if (!USERNAME_PATTERN.test(username)) {
    throw new Error('用户名只能包含英文字母、数字和下划线。')
  }

  return username
}

export function usernameToInternalEmail(value) {
  return `${normalizeUsername(value)}@${INTERNAL_AUTH_DOMAIN}`
}

export function roleFromAppMetadata(appMetadata) {
  return appMetadata?.role === 'admin' ? 'admin' : 'user'
}
