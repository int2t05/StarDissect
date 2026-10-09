# 渲染管线测试:证据块→结构化 HTML、token map→章节链、纯文本抽取(ADR-0007/0008)
from app.render import pipeline


def _sections(md):
    return pipeline.render(md)


def test_evidence_blocks_to_structured_html():
    md = "\n".join([
        "结论:鉴权在中间件层完成。",
        "> [source] internal/auth/middleware.py:42-58",
        "> [author] 见官方说明 (https://example.com/post, 2026-10-01)",
        "> [infer] 该设计为兼容多租户而设",
        "> [external] 相关讨论 (https://github.com/o/r/issues/7, 2026-10-02)",
        "> [unknown] 两处实现相互矛盾",
    ])
    html, sections, text = _sections(md)
    assert '<div class="ev ev-source" data-ref="internal/auth/middleware.py:42-58"' in html
    assert '<div class="ev ev-author"' in html and "https://example.com/post" in html
    assert '<div class="ev ev-infer"' in html and "分析推断" in html
    assert '<div class="ev ev-external"' in html
    assert '<div class="ev ev-unknown"' in html and "证据不足" in html


def test_plain_blockquote_untouched():
    md = "> 普通引用,不是证据块"
    html, _, _ = _sections(md)
    assert "ev ev-source" not in html and "普通引用" in html


def test_heading_map_builds_section_chain():
    md = "# 顶题\n\nintro\n\n## 系统设计\n\n内容甲\n\n### 数据流\n\n内容乙\n\n## 方案取舍\n\n内容丙"
    _, sections, _ = _sections(md)
    # h2 为章节,h3 为其子层级;path_chain=父序号链;line 来自 token map
    assert [s["title"] for s in sections] == ["系统设计", "数据流", "方案取舍"]
    assert sections[0]["line"] == 4  # 0 基,markdown-it map
    assert sections[1]["path_chain"] == "0/0" and sections[1]["seq"] == 1
    assert sections[2]["path_chain"] == "1" and sections[2]["seq"] == 2


def test_plain_text_skips_code():
    md = "段落甲 `inline_code` 尾\n\n```python\nx = 'block_code'\n```\n\n段落乙"
    _, _, text = _sections(md)
    assert "段落甲" in text and "段落乙" in text
    assert "inline_code" not in text and "block_code" not in text


def test_heading_anchors_injected():
    # h2/h3 必须带 id/data-seq,供目录/scrollspy/进度消费(ADR-0007)
    md = "## 系统设计\n\n内容\n\n### 数据流\n\n内容乙"
    html, sections, _ = _sections(md)
    assert 'data-seq="0"' in html and 'id="sec-0"' in html and 'data-seq="1"' in html


def test_mermaid_block_marked():
    # RPT-005:mermaid fence 输出专用容器(前端渲染+文字后备);严格断言防宽松误报
    md = "## 图\n\n```mermaid\ngraph TD; A-->B;\n```"
    html, _, _ = _sections(md)
    assert '<div class="mermaid">' in html
    assert '<pre><code class="mermaid' not in html


def test_typography_validator_rules():
    from app.render import validator

    v = validator.validate("这是GitHub直连的内容,测试。\n中文english混排\n第3章起点\n")
    rules = {x["rule"] for x in v}
    assert "UX-16 中英文间距" in rules  # 第 2 行「中文english」
    assert "UX-17 数字中文间距" in rules  # 第 3 行「第3章」
    # 白名单行豁免:含 GitHub 的行不报中英间距
    assert not [x for x in v if x["line"] == 1 and x["rule"].startswith("UX-16")]
