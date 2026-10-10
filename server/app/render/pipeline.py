# 渲染管线(ADR-0008):一次 markdown-it 解析,token 流同时派生
#   1) HTML(证据块语法→UX-43..47 结构) 2) h2/h3 章节+map 行号链(ADR-0007) 3) 跳过代码的纯文本(校验/索引共用)
# 参考:https://markdown-it-py.readthedocs.io/ — token.map 行区间(docs/using.md:229)
import html
import re

from markdown_it import MarkdownIt
from markdown_it.token import Token

# 证据块契约(docs/v1.0/tech.md §5):> [type] 内容,与 agent 提示词同步维护
EVIDENCE_RE = re.compile(r"^\[(source|author|infer|external|unknown)\]\s*(.+)$", re.S)
EVIDENCE_LABELS = {"source": "源码事实", "author": "作者说明", "infer": "分析推断", "external": "外部背景", "unknown": "证据不足"}

# 作者/外部背景的尾注 (url, 日期);解析失败则整体作正文
TAIL_RE = re.compile(r"^(.*?)\s*\(([^)]+),\s*([^)]+)\)\s*$", re.S)

_md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
_default_fence = _md.renderer.rules["fence"]


def _quote_mermaid_labels(src: str) -> str:
    # 确定性规范化:未加引号的节点标签补双引号——标签含 {} 等结构字符时 mermaid 必解析失败,
    # 引号内合法。模型输出不保证遵守写法契约,渲染层兜底保证存库即安全。
    return re.sub(r'([A-Za-z0-9_]+)\[(?!")([^\]\[\n"]+)\]', r'\1["\2"]', src)


def _fence_rule(self, tokens, idx, options, env):
    # mermaid 块输出专用容器(前端渲染+文字后备,RPT-005);其余 fence 走默认 <pre><code>
    # add_render_rule 会把函数绑定到 renderer(首参 self);捕获的默认规则已是绑定方法,调用不传 self
    t = tokens[idx]
    if t.info and t.info.strip() == "mermaid":
        body = html.escape(_quote_mermaid_labels(t.content))
        return f'<div class="mermaid">\n{body}</div>\n'
    return _default_fence(tokens, idx, options, env)


_md.add_render_rule("fence", _fence_rule)


def _evidence_html(kind: str, body: str) -> str:
    label = EVIDENCE_LABELS[kind]
    attrs = f'class="ev ev-{kind}"'
    if kind == "source":
        return f'<div {attrs} data-ref="{html.escape(body, quote=True)}"><span class="ev-label">{label}</span><code class="ev-ref">{html.escape(body)}</code></div>'
    tail = TAIL_RE.match(body)
    link = ""
    if kind in ("author", "external") and tail:
        text, url, date = tail.group(1).strip(), tail.group(2).strip(), tail.group(3).strip()
        link = f'<a href="{html.escape(url, quote=True)}" rel="noopener">{html.escape(url)}</a><span class="ev-date">查阅 {html.escape(date)}</span>'
        extra = f' data-url="{html.escape(url, quote=True)}"'
    else:
        text, extra = body.strip(), ""
    return f'<div {attrs}{extra}><span class="ev-label">{label}</span><p>{html.escape(text)}</p>{link}</div>'


def _plain_of_inline(token: Token) -> str:
    # 行内纯文本:跳过行内代码(代码内容不进校验/索引流,规则源=UIUX §3 校验输入)
    parts = []
    for child in token.children or []:
        if child.type != "code_inline":
            parts.append(child.content)
    return "".join(parts)


def _split_evidence(tokens: list[Token]) -> list[Token]:
    # 把证据引用块整体替换为 html_block token;普通引用块原样保留
    out: list[Token] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t.type != "blockquote_open":
            out.append(t)
            i += 1
            continue
        depth, j = 1, i + 1
        while depth and j < len(tokens):
            depth += {"blockquote_open": 1, "blockquote_close": -1}.get(tokens[j].type, 0)
            j += 1
        inner = [x for x in tokens[i + 1 : j - 1] if x.type == "inline"]
        if inner:
            # 契约:一个证据块一行;连续 > 行会被 lazy continuation 合并,故按行解析,
            # 未命中行保留为普通段落,不丢内容
            divs: list[str] = []
            leftovers: list[str] = []
            for line in inner[0].content.splitlines():
                m = EVIDENCE_RE.match(line)
                if m:
                    divs.append(_evidence_html(m.group(1), m.group(2)))
                elif line.strip():
                    leftovers.append(line)
            if divs:
                if leftovers:
                    divs.append(f"<p>{html.escape(chr(10).join(leftovers))}</p>")
                block = Token("html_block", "", 0)
                block.content = "\n".join(divs)
                out.append(block)
                i = j
                continue
        out.extend(tokens[i:j])
        i = j
    return out


def _sections_and_text(tokens: list[Token]) -> tuple[list[dict], str]:
    # 章节:h2 开新章(链=章序),h3 为子节(链=父链/子序);line 取 token.map 首行
    # 同时向 heading_open 注入 id/data-seq 锚点——目录/scrollspy/进度恢复的消费契约(ADR-0007)
    sections: list[dict] = []
    text_parts: list[str] = []
    h2_idx = h3_idx = -1
    for t in tokens:
        if t.type in ("code_block", "fence"):
            continue  # 图/代码不进纯文本流;mermaid 容器由专用 fence 规则输出
        if t.type == "heading_open" and t.tag in ("h2", "h3"):
            title_t = tokens[tokens.index(t) + 1]
            if t.tag == "h2":
                h2_idx += 1
                h3_idx = -1
                chain = str(h2_idx)
            else:
                h3_idx += 1
                chain = f"{h2_idx}/{h3_idx}" if h2_idx >= 0 else str(h3_idx)
            seq = len(sections)
            t.attrs = {"id": f"sec-{seq}", "data-seq": str(seq)}
            sections.append({
                "seq": seq,
                "level": int(t.tag[1]),
                "title": title_t.content.strip(),
                "line": t.map[0],
                "path_chain": chain,
                "text": "",
            })
            text_parts.append(title_t.content.strip())
        elif t.type == "inline":
            plain = _plain_of_inline(t)
            if sections:
                sections[-1]["text"] = (sections[-1]["text"] + "\n" + plain).strip()
            text_parts.append(plain)
    return sections, "\n".join(p for p in text_parts if p)


def render(markdown: str) -> tuple[str, list[dict], str]:
    """返回 (HTML, 章节链, 跳过代码的纯文本)。章节链元素:seq/level/title/line/path_chain/text。"""
    tokens = _split_evidence(_md.parse(markdown))
    sections, plain = _sections_and_text(tokens)
    html_out = _md.renderer.render(tokens, _md.options, {})
    return html_out, sections, plain
