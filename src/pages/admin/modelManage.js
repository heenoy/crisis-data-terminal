import { bindAdminPlaceholder, renderAdminPlaceholder } from './placeholder.js'

export function renderAdminModelManage() {
  return renderAdminPlaceholder({
    kicker: 'ADMIN_PORTAL / MODEL CONTROL',
    title: '模型管理',
    description: '预测模型、训练时间与评估指标管理入口',
  })
}

export const initAdminModelManage = bindAdminPlaceholder
