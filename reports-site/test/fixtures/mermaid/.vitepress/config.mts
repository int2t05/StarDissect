import { defineConfig } from 'vitepress'
import siteConfig from '../../../../.vitepress/config.mts'

// 浏览器验收页独立于数据库导出的 reports-site/src。
export default defineConfig({
  ...siteConfig,
  base: '/',
  srcDir: '.',
  outDir: '.vitepress/dist',
  title: 'Mermaid 浏览器验收',
})
