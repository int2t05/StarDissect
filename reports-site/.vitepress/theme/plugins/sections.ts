/**
 * 章节锚点规则：h2/h3 注入 `id="sec-N"` 与 `data-seq=N`（DOM 序）。
 * 从服务端管线（app/render/pipeline.py 的 _sections_and_text 注入逻辑）移植——
 * 进度恢复与 scrollspy 的消费契约（ADR-0007）：`.vp-doc [data-seq]` 即章节锚点。
 * VitePress 的 outline 优先读 token 上已有的 id，目录链接因此与锚点一致。
 * 行内 {{ 防护在此一并打标（正文 text/code_inline 里的 {{ 不许被 Vue 吃掉）。
 */
import type MarkdownIt from 'markdown-it'
import type StateCore from 'markdown-it/lib/rules_core/state_core.mjs'
import { protectMustache } from './evidence'

export default function sections(md: MarkdownIt): void {
  md.core.ruler.push('stardissect_sections', (state: StateCore) => {
    let seq = 0
    for (const token of state.tokens) {
      if (token.type === 'heading_open' && (token.tag === 'h2' || token.tag === 'h3')) {
        token.attrSet('id', `sec-${seq}`)
        token.attrSet('data-seq', String(seq))
        seq += 1
      } else if (token.type === 'inline' && token.children) {
        protectMustache(token.children)
      }
    }
  })
}
