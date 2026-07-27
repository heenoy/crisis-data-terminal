export function renderAdminPlaceholder({ kicker, title, description }) {
  return `
    <section class="vault-console vault-console--subpage" aria-label="${title}">
      <div class="admin-portal admin-portal--placeholder">
        <header class="admin-portal__header">
          <div>
            <p class="vault-kicker">[ ${kicker} ]</p>
            <h1>${title}</h1>
            <p>${description}</p>
          </div>
        </header>
        <div class="admin-placeholder-status">
          <strong>MODULE STATUS: RESERVED</strong>
          <span>该模块已完成路由与权限接入，业务功能将在下一阶段开发。</span>
        </div>
        <nav class="admin-module-grid admin-module-grid--compact">
          <button type="button" data-route="admin/dashboard">
            <strong>返回管理首页</strong><span>ADMIN DASHBOARD</span>
          </button>
        </nav>
      </div>
    </section>
  `
}

export function bindAdminPlaceholder(onNavigate) {
  document.querySelectorAll('.admin-module-grid [data-route]').forEach((button) => {
    button.addEventListener('click', () => onNavigate?.(button.dataset.route))
  })
}
