/** Mermaid 围栏渲染为源码容器；pre 保留语法所需换行，其余围栏仍交给 Shiki。 */
import { escapeHtml } from 'markdown-it/lib/common/utils.mjs'
import { normalizeMermaidSource } from '../mermaid.js'

/** 把 Mermaid 围栏交给客户端统一渲染。 */
export default function mermaidFence(md) {
  const defaultFence = md.renderer.rules.fence
  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    if (token.info && token.info.trim() === 'mermaid') {
      const body = escapeHtml(normalizeMermaidSource(token.content))
      // pre 保存 fence 内的行边界，普通 div 的 textContent 会合并 Mermaid 声明。
      return `<div class="mermaid"><pre class="mermaid-source">${body}</pre></div>\n`
    }
    return defaultFence
      ? defaultFence(tokens, idx, options, env, self)
      : self.renderToken(tokens, idx, options)
  }
}
