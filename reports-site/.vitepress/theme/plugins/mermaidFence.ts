/**
 * mermaid 围栏规则：`​```mermaid` 块输出专用容器（前端渲染 + 文字后备，RPT-005），
 * 其余围栏走 VitePress 的默认规则（Shiki 高亮 + v-pre 原样保留）。
 * 从服务端管线（app/render/pipeline.py 的 _quote_mermaid_labels/_fence_rule）移植；
 * 标签补引号的确定性修复在客户端渲染时还有一道（renderMermaid 内的 repaired）。
 */
import type MarkdownIt from 'markdown-it'
import { escapeHtml } from 'markdown-it/lib/common/utils.mjs'

/** 确定性规范化:未加引号的节点标签补双引号——标签含 {} 等结构字符时 mermaid 必解析失败,
 * 引号内合法。模型输出不保证遵守写法契约,渲染层兜底保证存库即安全。 */
function quoteMermaidLabels(src: string): string {
  return src.replace(/([A-Za-z0-9_]+)\[(?!")([^\]\[\n"]+)\]/g, '$1["$2"]')
}

export default function mermaidFence(md: MarkdownIt): void {
  const defaultFence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const t = tokens[idx]
    if (t.info && t.info.trim() === 'mermaid') {
      const body = escapeHtml(quoteMermaidLabels(t.content))
      return `<div class="mermaid">\n${body}</div>\n`
    }
    return defaultFence ? defaultFence(tokens, idx, options, env, self) : self.renderToken(tokens, idx, options)
  }
}
