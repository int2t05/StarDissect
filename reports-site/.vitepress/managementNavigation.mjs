// 管理 SPA 在站点根路径；target=_self 让浏览器接管跨目录跳转。
export const managementNavigation = [
  { text: '阅读中心', link: '/../#/reading', target: '_self' },
  { text: '仓库库', link: '/../#/repos', target: '_self' },
  { text: '分析管理', link: '/../#/analysis', target: '_self' },
  { text: '系统设置', link: '/../#/settings', target: '_self' },
]

// 兼容已分享的 /reports/#/页面 地址；报告章节锚点不匹配此规则。
export function managementRouteTarget(pathname, hash) {
  if (pathname !== '/reports' && pathname !== '/reports/') return null
  if (!/^#\/(reading|repos|analysis|settings)\/?$/.test(hash)) return null
  return `/${hash}`
}
