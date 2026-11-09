import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import Layout from './components/ReportShell.vue'
import { managementRouteTarget } from '../managementNavigation.mjs'
import './custom.css'

// 默认主题 + 报告页的 DOM 加工（证据合并、mermaid 渲染、放大层）与工具条
if (typeof window !== 'undefined') {
  const target = managementRouteTarget(window.location.pathname, window.location.hash)
  if (target) window.location.replace(target)
}

export default {
  extends: DefaultTheme,
  Layout,
} satisfies Theme
