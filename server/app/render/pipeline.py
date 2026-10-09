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
    # 行内纯文本:跳过行内代码(代码内容不进校验/索引流,UX-52)
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
    sections: list[dict] = []
    text_parts: list[str] = []
    h2_idx = h3_idx = -1
    for t in tokens:
        if t.type in ("code_block", "fence"):
            continue
        if t.type == "heading_open" and t.tag in ("h2", "h3"):
            title_t = tokens[tokens.index(t) + 1]
            if t.tag == "h2":
                h2_idx += 1
                h3_idx = -1
                chain = str(h2_idx)
            else:
                h3_idx += 1
                chain = f"{h2_idx}/{h3_idx}" if h2_idx >= 0 else str(h3_idx)
            sections.append({
                "seq": len(sections),
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
