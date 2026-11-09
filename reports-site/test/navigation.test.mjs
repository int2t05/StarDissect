import assert from 'node:assert/strict'
import test from 'node:test'
import { managementNavigation, managementRouteTarget } from '../.vitepress/managementNavigation.mjs'

const origin = 'https://stardissectint2t.vip.cpolar.cn'
const routes = ['reading', 'repos', 'analysis', 'settings']

test('报告站管理导航绕过 VitePress 并落到根路径 SPA', () => {
  assert.deepEqual(
    managementNavigation.map(({ text, target, link }) => ({ text, target, link })),
    [
      { text: '阅读中心', target: '_self', link: '/../#/reading' },
      { text: '仓库库', target: '_self', link: '/../#/repos' },
      { text: '分析管理', target: '_self', link: '/../#/analysis' },
      { text: '系统设置', target: '_self', link: '/../#/settings' },
    ],
  )

  for (const { link } of managementNavigation) {
    const renderedHref = `/reports/${link.slice(1)}`
    const destination = new URL(renderedHref, origin)
    assert.equal(destination.pathname, '/')
    assert.equal(destination.hash, link.slice(link.indexOf('#')))
  }
})

test('报告站中的旧管理 hash 地址重定向到根路径', () => {
  for (const route of routes) {
    assert.equal(managementRouteTarget('/reports/', `#/${route}`), `/#/${route}`)
    assert.equal(managementRouteTarget('/reports', `#/${route}`), `/#/${route}`)
  }

  assert.equal(managementRouteTarget('/reports/', '#sec-0'), null)
  assert.equal(managementRouteTarget('/reports/54yyyu__zotero-mcp/127/', '#/analysis'), null)
  assert.equal(managementRouteTarget('/', '#/analysis'), null)
})
