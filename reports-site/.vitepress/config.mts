import { defineConfig } from 'vitepress'
import evidence from './theme/plugins/evidence'
import mermaidFence from './theme/plugins/mermaidFence'
import sections from './theme/plugins/sections'

// 报告阅读站：SPA 瘦身为管理面，阅读面整体迁到这里（ADR-0009）
// 与 FluxSift 阅读站同版本（package.json 钉死）、同 Shiki 主题：两站阅读面统一
export default defineConfig({
  lang: 'zh-CN',
  title: 'StarDissect 报告',
  description: 'GitHub star 仓库的深度分析报告',
  srcDir: 'src',
  outDir: 'dist',
  base: '/reports/',
  ignoreDeadLinks: true,
  markdown: {
    // 外部来源的正文（模型产出的报告）不许当模板：裸 HTML 一律转义，与服务端管线同一条底线
    html: false,
    theme: { light: 'github-light', dark: 'github-dark' },
    // 章节 id 由我们的 sections 规则接管（sec-N，进度/scrollspy 的消费契约），
    // anchor 插件的 permalink 小 # 指向它自己的 slug、与 sec-N 对不上，关掉
    anchor: { permalink: false },
    config(md) {
      // 挂在内置插件之后：章节锚点覆盖 anchor 插件的 id；证据块与 mermaid 容器是自有语法
      md.use(sections)
      md.use(evidence)
      md.use(mermaidFence)
    },
  },
  themeConfig: {
    outline: [2, 3],
    outlineLabel: '本页大纲',
    darkModeSwitchLabel: '主题',
    docFooter: { prev: '上一篇', next: '下一篇' },
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: { buttonText: '搜索报告', buttonAriaLabel: '搜索' },
              modal: {
                noResultsText: '没有结果',
                resetButtonTitle: '清空条件',
                footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
              },
            },
          },
        },
      },
    },
  },
})
