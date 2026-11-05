/**
 * 证据块规则（markdown-it 插件）：blockquote 证据语法 → details.ev 折叠块。
 *
 * 从服务端管线（app/render/pipeline.py 的 _split_evidence/_evidence_details）逐条移植，
 * 服务端管线保留供章节提取/校验/RSS/导出（ADR-0009）——这里是阅读站自己的渲染层。
 * 契约：`> [type] 内容`，连续证据（混合类型）合并为一个折叠块，源码条目带 data-refs
 * 供前端注入锚定 commit 的 GitHub 链接；不合准入的条目降级还原为正文段落。
 * 另带 Vue 插值防护：正文 text/行内代码里的 `{{` 输出成 &#123;&#123;（markdown 会被
 * Vue 编译，插值轻则空白重则构建失败；围栏代码由 VitePress 的 v-pre 罩住）。
 */
import type MarkdownIt from 'markdown-it'
import type StateCore from 'markdown-it/lib/rules_core/state_core.mjs'
import Token from 'markdown-it/lib/token.mjs'
import { escapeHtml } from 'markdown-it/lib/common/utils.mjs'

// 证据块契约(docs/v1.0/tech.md §5):> [type] 内容,与 agent 提示词同步维护
const EVIDENCE_RE = /^\[(source|author|infer|external|unknown)\]\s*([\s\S]+)$/
const EVIDENCE_LABELS: Record<string, string> = {
  source: '源码事实',
  author: '作者说明',
  infer: '分析推断',
  external: '外部背景',
  unknown: '证据不足',
}

// 证据块准入:source 正文必须是「路径:行号」形态;infer 超长视为叙述误标。
// 不合准入的条目降级还原为正文段落——证据块只放出处佐证,主体永远是叙述(REQ-RPT-001/002)
const REF_SHAPE = /^[A-Za-z0-9_./\-]+:\d+(-\d+)?$/
const DEMOTE_CHARS = 120

const TAIL = /^(.*?)\s*\(([^)]+),\s*([^)]+)\)\s*$/s

const MUSTACHE = /\{\{/g

export default function evidence(md: MarkdownIt): void {
  md.core.ruler.push('stardissect_evidence', (state: StateCore) => {
    state.tokens = splitEvidence(state.tokens)
  })
  const textRule = md.renderer.rules.text
  md.renderer.rules.text = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    if (token.meta?.sdBraceEscaped) return braceEscape(token.content)
    return textRule ? textRule(tokens, idx, options, env, self) : self.renderToken(tokens, idx, options)
  }
  const codeInlineRule = md.renderer.rules.code_inline
  md.renderer.rules.code_inline = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    if (token.meta?.sdBraceEscaped) return `<code>${braceEscape(token.content)}</code>`
    return codeInlineRule ? codeInlineRule(tokens, idx, options, env, self) : ''
  }
}

/** 输出成 &#123;&#123;：Vue 在「原始模板串」上找插值，实体解码后才变成 {{，因此不会被吃。 */
function braceEscape(raw: string): string {
  return escapeHtml(raw).replace(MUSTACHE, '&#123;&#123;')
}

/** 证据块自拼 HTML 里的模型文本出口：escapeHtml 之外还要拆 {{——
 * html_block 绕过正文 text 通道，插值防护（protectMustache）罩不到这里。 */
function esc(raw: string): string {
  return escapeHtml(raw).replace(MUSTACHE, '&#123;&#123;')
}

/** 折叠体内单条证据:自带标签,正文片段。 */
function evidenceEntry(kind: string, body: string): string {
  const label = EVIDENCE_LABELS[kind]
  if (kind === 'source') {
    return `<div class="ev-item"><span class="ev-label">${label}</span><code class="ev-ref">${esc(body.trim())}</code></div>`
  }
  const tail = TAIL.exec(body)
  let text = body.trim()
  let link = ''
  if ((kind === 'author' || kind === 'external') && tail) {
    text = tail[1].trim()
    const url = tail[2].trim()
    const date = tail[3].trim()
    link = `<p><a href="${esc(url)}" rel="noopener">${esc(url)}</a><span class="ev-date">${esc(date)}</span></p>`
  }
  return `<div class="ev-item"><span class="ev-label">${label}</span><p>${esc(text)}</p>${link}</div>`
}

/** 连续证据(混合类型)合并为一个折叠块:单行摘要「证据 ×n」,展开看逐条标签与内容。
 * 源码条目带 data-refs 供前端注入锚定 commit 的 GitHub 链接。 */
function evidenceDetails(entries: Array<[string, string]>): string {
  const n = entries.length
  const firstKind = entries[0][0]
  const refs = entries.filter(([k]) => k === 'source').map(([, b]) => b.trim())
  const refsAttr = refs.length
    ? ` data-refs="${esc(refs.join(String.fromCharCode(31)))}"`
    : ''
  const items = entries.map(([k, b]) => evidenceEntry(k, b)).join('')
  const firstLabel = EVIDENCE_LABELS[firstKind]
  const firstExcerpt = entries[0][1].trim().replace(/\n/g, ' ')
  const snip = firstExcerpt.slice(0, 40) + (firstExcerpt.length > 40 ? '…' : '')
  const countChip = n > 1 ? `<span class="ev-count">×${n}</span>` : ''
  const summary = `<span class="ev-label">${firstLabel}</span><span class="ev-snip">${esc(snip)}</span>${countChip}`
  return (
    `<details class="ev ev-${firstKind}"${refsAttr}>` +
    `<summary>${summary}</summary>` +
    `<div class="ev-body">${items}</div></details>`
  )
}

/** 把证据引用块整体替换为 html_block token;普通引用块原样保留。 */
function splitEvidence(tokens: Token[]): Token[] {
  const out: Token[] = []
  let i = 0
  while (i < tokens.length) {
    const t = tokens[i]
    if (t.type !== 'blockquote_open') {
      out.push(t)
      i += 1
      continue
    }
    let depth = 1
    let j = i + 1
    while (depth && j < tokens.length) {
      depth += { blockquote_open: 1, blockquote_close: -1 }[tokens[j].type] ?? 0
      j += 1
    }
    const inner = tokens.slice(i + 1, j - 1).filter(x => x.type === 'inline')
    if (inner.length) {
      // 契约:一个证据块一行;连续 > 行会被 lazy continuation 合并(空行还会拆出
      // 多个 inline),故遍历全部 inline 按行解析,未命中行保留为普通段落,不丢内容
      const entries: Array<[string, string]> = []
      const leftovers: string[] = []
      for (const x of inner) {
        for (const line of x.content.split('\n')) {
          const m = EVIDENCE_RE.exec(line)
          if (m) entries.push([m[1], m[2]])
          else if (line.trim()) leftovers.push(line)
        }
      }
      if (entries.length) {
        // 准入过滤:叙述误标(source 非「路径:行号」/ infer 超长)还原为正文段落
        const fold: Array<[string, string]> = []
        const demoted: string[] = []
        for (const [kind, body] of entries) {
          const text = body.trim()
          if (kind === 'source' && !REF_SHAPE.test(text)) demoted.push(text)
          else if (kind === 'infer' && text.length > DEMOTE_CHARS) demoted.push(text)
          else fold.push([kind, body])
        }
        if (fold.length) {
          const block = new Token('html_block', '', 0)
          block.content = evidenceDetails(fold)
          out.push(block)
        }
        // 引用块内非证据行与降级叙述重建为真段落 token:HTML 与纯文本流都保留。
        // 此 token 在 sections 规则(先行)之后创建,插值防护要在这里自己补标
        if (leftovers.length || demoted.length) {
          const allText = [...leftovers, ...demoted].join('\n')
          const textToken = new Token('inline', '', 0)
          textToken.content = allText
          const text = new Token('text', '', 0)
          text.content = allText
          if (allText.includes('{{')) {
            text.meta = { sdBraceEscaped: true }
          }
          textToken.children = [text]
          out.push(new Token('paragraph_open', 'p', 1), textToken, new Token('paragraph_close', 'p', -1))
        }
        i = j
        continue
      }
    }
    out.push(...tokens.slice(i, j))
    i = j
  }
  return out
}

// 供 core 规则复用的行内 {{ 防护:给含 {{ 的 text/code_inline 打标记
export function protectMustache(children: Token[]): void {
  for (const child of children) {
    if ((child.type === 'text' || child.type === 'code_inline') && child.content.includes('{{')) {
      if (!child.meta) child.meta = {}
      child.meta.sdBraceEscaped = true
    }
  }
}
