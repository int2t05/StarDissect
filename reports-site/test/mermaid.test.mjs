import assert from 'node:assert/strict'
import test from 'node:test'
import MarkdownIt from 'markdown-it'
import mermaid from 'mermaid'
import { normalizeMermaidSource } from '../.vitepress/theme/mermaid.js'
import mermaidFence from '../.vitepress/theme/plugins/mermaidFence.js'

test('补全未加引号的节点标签并保持转换幂等', () => {
  const source = 'graph TB\nA[节点 {结构}] --> B[下一步]'
  const normalized = normalizeMermaidSource(source)

  assert.equal(normalized, 'graph TB\nA["节点 {结构}"] --> B["下一步"]')
  assert.equal(normalizeMermaidSource(normalized), normalized)
})

test('保留已有引号和 HTML 换行标签', () => {
  const source = 'graph TB\nA["已有标签<br/>第二行"] --> B[普通标签]'
  assert.equal(
    normalizeMermaidSource(source),
    'graph TB\nA["已有标签<br/>第二行"] --> B["普通标签"]',
  )
})

test('报告中的中文分层组件图保持结构与换行声明', () => {
  const source = `graph TB
subgraph L1["入口层"]
  CLI["zotero-mcp serve"]
  SA["zotero-cli"]
end
subgraph L2["工具层"]
  TOOLS["13 个工具模块<br/>import 即注册"]
  TS["toolsets.py<br/>工具面裁剪"]
end
subgraph L3["客户端与端口层"]
  CLIENT["client.py<br/>pyzotero 封装与全局锁"]
  PORT["library.py 读端口"]
  LDB["local_db.py<br/>SQLite 直读"]
end
CLI --> TOOLS
SA --> TS
TOOLS --> CLIENT
TS --> CLIENT
CLIENT --> PORT
CLIENT --> LDB`

  assert.equal(normalizeMermaidSource(source), source)
})

test('Markdown 围栏用 pre 保存多行源码并转义标签', () => {
  const markdown = '```mermaid\ngraph TB\nA[节点 {结构}] --> B[下一步]\n```'
  const html = new MarkdownIt().use(mermaidFence).render(markdown)

  assert.match(html, /<div class="mermaid"><pre class="mermaid-source">graph TB\n/)
  assert.match(html, /A\[&quot;节点 \{结构\}&quot;\] --&gt; B\[&quot;下一步&quot;\]/)
})

test('无效 Mermaid 语法会被解析器拒绝', async () => {
  await assert.rejects(() => mermaid.parse('graph TB\nA -->'))
})
