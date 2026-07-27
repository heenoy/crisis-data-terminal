import { bindAdminPlaceholder, renderAdminPlaceholder } from './placeholder.js'

export function renderAdminUserManage() {
  return renderAdminPlaceholder({
    kicker: 'ADMIN_PORTAL / USER CONTROL',
    title: '用户管理',
    description: '注册用户与账号状态管理入口',
  })
}

export const initAdminUserManage = bindAdminPlaceholder
