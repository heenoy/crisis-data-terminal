import { signIn, signUp } from './auth.js'

let activeMode = 'login'

function setError(message) {
  const el = document.getElementById('auth-error')
  if (!el) return
  el.textContent = message || ''
  el.classList.toggle('is-active', !!message)
}

function setLoading(loading) {
  const submit = document.getElementById('auth-submit')
  if (submit) {
    submit.disabled = loading
    submit.textContent = loading ? '[ PROCESSING... ]' : activeMode === 'login' ? '[ SIGN IN ]' : '[ REGISTER ]'
  }
}

function updateModeUI() {
  const submit = document.getElementById('auth-submit')
  const hint = document.getElementById('auth-mode-hint')
  const displayNameField = document.getElementById('auth-display-name-field')

  document.querySelectorAll('[data-auth-tab]').forEach((tab) => {
    tab.classList.toggle('is-active', tab.dataset.authTab === activeMode)
  })

  if (displayNameField) {
    displayNameField.hidden = activeMode !== 'register'
  }

  if (submit) {
    submit.textContent = activeMode === 'login' ? '[ SIGN IN ]' : '[ REGISTER ]'
  }

  if (hint) {
    hint.textContent =
      activeMode === 'login'
        ? '输入用户名与密码以接入 Crisis Data Terminal。'
        : '创建普通用户账号，用户名支持 3–24 位字母、数字和下划线。'
  }
}

export function renderAuthPage() {
  return `
    <section class="survivor-auth-shell" aria-label="Crisis Data Terminal access">
      <div class="survivor-auth-panel">
        <p class="survivor-auth-kicker">[ CRISIS DATA / ACCESS GATE ]</p>
        <h1>终端接入<span>CRISIS DATA TERMINAL / 应急灾害档案终端</span></h1>
        <div class="survivor-auth-copy">
          <p id="auth-mode-hint">输入用户名与密码以接入 Crisis Data Terminal。</p>
          <p>Disaster Event Archive · 未授权访问将被记录并阻断。</p>
        </div>

        <div class="survivor-auth-tabs" role="tablist" aria-label="认证模式">
          <button type="button" class="survivor-auth-tab is-active" data-auth-tab="login" role="tab">登录</button>
          <button type="button" class="survivor-auth-tab" data-auth-tab="register" role="tab">注册</button>
        </div>

        <form class="survivor-auth-form" id="auth-form" novalidate>
          <label>
            <span>USERNAME / 用户名</span>
            <input type="text" name="username" autocomplete="username" required minlength="3" maxlength="24" pattern="[A-Za-z0-9_]+" placeholder="vault_user" />
          </label>
          <label id="auth-display-name-field" hidden>
            <span>DISPLAY NAME / 昵称</span>
            <input type="text" name="display_name" autocomplete="nickname" placeholder="操作员名称" />
          </label>
          <label>
            <span>PASSWORD / 密码</span>
            <input type="password" name="password" autocomplete="current-password" required minlength="6" placeholder="******" />
          </label>
          <p class="survivor-auth-error" id="auth-error" role="alert"></p>
          <div class="survivor-auth-actions survivor-auth-actions--stack">
            <button type="submit" id="auth-submit">[ SIGN IN ]</button>
            <button type="button" id="auth-back">[ RETURN ]</button>
          </div>
        </form>
      </div>
    </section>
  `
}

export function bindAuthPage({ onSuccess, onBack }) {
  activeMode = 'login'
  setError('')
  updateModeUI()

  document.querySelectorAll('[data-auth-tab]').forEach((tab) => {
    tab.addEventListener('click', () => {
      activeMode = tab.dataset.authTab
      setError('')
      updateModeUI()
    })
  })

  document.getElementById('auth-back')?.addEventListener('click', () => onBack?.())

  document.getElementById('auth-form')?.addEventListener('submit', async (e) => {
    e.preventDefault()
    setError('')

    const form = e.currentTarget
    const username = form.username.value
    const password = form.password.value
    const displayName = form.display_name?.value.trim() || username

    if (!username || !password) {
      setError('请填写用户名和密码。')
      return
    }

    if (activeMode === 'register' && !displayName) {
      setError('请填写昵称。')
      return
    }

    setLoading(true)
    try {
      if (activeMode === 'login') {
        const { error } = await signIn(username, password)
        if (error) {
          setError(error.message || '登录失败，请稍后重试。')
          return
        }
        onSuccess?.()
        return
      }

      const { error } = await signUp(username, password, displayName)
      if (error) {
        setError(error.message || '注册失败，请稍后重试。')
        return
      }

      setError('注册成功，请使用新账号登录。')
      activeMode = 'login'
      form.password.value = ''
      updateModeUI()
    } catch {
      setError('认证请求失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  })
}
