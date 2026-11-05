import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme'
import Layout from './components/ReportShell.vue'
import './custom.css'

// 默认主题 + 报告页的 DOM 加工（证据合并、mermaid 渲染、放大层）与工具条
export default {
  extends: DefaultTheme,
  Layout,
} satisfies Theme
