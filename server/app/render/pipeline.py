# 渲染管线(ADR-0008):一次 markdown-it 解析,token 流同时派生
#   1) HTML(证据块语法→UX-43..47 结构,默认折叠) 2) h2/h3 章节+map 行号链+锚点(ADR-0007)
#   3) 跳过代码的纯文本(校验/索引共用)
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

_KNOWN_LANGS = ("mermaid", "python", "json", "bash", "sh", "shell", "js", "ts", "javascript",
                "typescript", "yaml", "yml", "sql", "text", "ini", "html", "css", "c", "cpp", "go", "rs", "diff")

_md = MarkdownIt("commonmark").enable(["table", "strikethrough"])
_default_fence = _md.renderer.rules["fence"]


def _normalize_fences(md: str) -> str:
    """围栏独立性整形:``` 必须独立成行。修复模型把围栏写进段落句中的情况,
    否则整段被当正文,图/代码块失效。规则:行中 ``` 前补空行;开围栏语言标注后
    的同行内容换行;行首非已知语言的 ``` 视为收围栏残留,与后文拆行。"""
    md = re.sub(r"(?m)(?<!\n)```", "\n\n```", md)  # 行中 ``` 前补空行
    langs = "|".join(_KNOWN_LANGS)
    md = re.sub(rf"(?m)^```({langs})[ \t]+(?=\S)", r"```\1\n", md)  # 开围栏语言后换行
    md = re.sub(rf"(?m)^```[ \t]*(?!({langs})\b|[ \t]*$)([^\n]+)$", r"```\n\2", md)  # 收围栏残留拆行
    md = re.sub(r"(?m)^(?!```)(.+?)```[ \t]*$", r"\1\n```", md)  # 行中收围栏 → 前置换行
    return md


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
    # 证据块默认折叠(details/summary):主体保持文字流,证据收敛为单行标记(UX-03 标签可见)
    label = EVIDENCE_LABELS[kind]
    excerpt = body.strip().replace("\n", " ")[:48] + ("…" if len(body.strip()) > 48 else "")
    if kind == "source":
        summary_inner = f'<code class="ev-ref">{html.escape(body.strip())}</code>'
        body_inner = '<p class="ev-src-hint"></p>'  # 前端按 commit 锚点补「在 GitHub 打开」链接
        attrs = f' data-ref="{html.escape(body.strip(), quote=True)}"'
    else:
        tail = TAIL_RE.match(body)
        text, link, extra = body.strip(), "", ""
        if kind in ("author", "external") and tail:
            text = tail.group(1).strip()
            url, date = tail.group(2).strip(), tail.group(3).strip()
            link = f'<p><a href="{html.escape(url, quote=True)}" rel="noopener">{html.escape(url)}</a><span class="ev-date">{html.escape(date)}</span></p>'
            extra = f' data-url="{html.escape(url, quote=True)}"'
        summary_inner = f'<span class="ev-snip">{html.escape(excerpt)}</span>'
        body_inner = f'<p>{html.escape(text)}</p>{link}'
        attrs = extra
    return (
        f'<details class="ev ev-{kind}"{attrs}>'
        f'<summary><span class="ev-label">{label}</span>{summary_inner}</summary>'
        f'<div class="ev-body">{body_inner}</div></details>'
    )


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
    tokens = _split_evidence(_md.parse(_normalize_fences(markdown)))
    sections, plain = _sections_and_text(tokens)
    html_out = _md.renderer.render(tokens, _md.options, {})
    return html_out, sections, plain
