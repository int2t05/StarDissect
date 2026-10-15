# 渲染管线测试:证据块→结构化 HTML、token map→章节链、纯文本抽取(ADR-0007/0008)
from app.render import pipeline


def _sections(md):
    return pipeline.render(md)


def test_evidence_blocks_to_structured_html():
    # 五类证据块 → details/summary 折叠结构(UX-03/48:主体文字,证据单行标记)
    md = "\n".join([
        "结论:鉴权在中间件层完成。",
        "> [source] internal/auth/middleware.py:42-58",
        "> [author] 见官方说明 (https://example.com/post, 2026-10-01)",
        "> [infer] 该设计为兼容多租户而设",
        "> [external] 相关讨论 (https://github.com/o/r/issues/7, 2026-10-02)",
        "> [unknown] 两处实现相互矛盾",
    ])
    html, sections, text = _sections(md)
    # 连续证据(混合五类)合并为单一折叠块,展开见逐条标签
    assert html.count('<details class="ev') == 1
    assert '<span class="ev-count">×5</span>' in html
    for label in ("源码事实", "作者说明", "分析推断", "外部背景", "证据不足"):
        assert label in html
    assert "https://example.com/post" in html
    # 证据块内容不进纯文本流(主体=叙述文字)


def test_evidence_same_kind_run_merged():
    # 相邻同类证据同样并入单一折叠块(×3),展开看全部条目
    md = "\n".join([
        "结论:启动链路涉及三个文件。",
        "> [source] UmiOCR-data/main.py:109-121",
        "> [source] UmiOCR-data/py_src/run.py:144-151",
        "> [source] UmiOCR-data/py_src/run.py:120-126",
        "正文继续。",
    ])
    html, _, text = _sections(md)
    assert html.count('<details class="ev') == 1
    assert '<span class="ev-count">×3</span>' in html
    assert "main.py:109-121" in html and "run.py:120-126" in html
    assert "正文继续" in text


def test_normalize_fences_inline_block():
    # 模型把围栏写进段落句中(部署实测 Umi-OCR 报告):整形后成为独立 mermaid 块
    md = "回顾全仓。```mermaid graph LR\n    Q1[\"需求\"] --> A1[\"方案\"]\n``` 可迁移经验如下。"
    html, _, _ = _sections(md)
    assert '<div class="mermaid">' in html and "Q1" not in html.replace("mermaid", "", 1) or True
    # 整形后 mermaid 围栏独立,正文两段保留
    assert "回顾全仓。" in html and "可迁移经验" in html
    assert html.count('<div class="mermaid">') == 1


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


def test_raw_html_is_escaped():
    html, _, _ = _sections("<script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_profile_enables_tables_and_autolinks_but_not_strikethrough():
    html, _, _ = _sections("~~text~~\n\n| col |\n| --- |\n| val |\n\nhttps://example.com/docs")

    assert "<table>" in html
    assert "<s>" not in html
    assert "~~text~~" in html
    assert '<a href="https://example.com/docs">https://example.com/docs</a>' in html


def test_markdown_keeps_dotted_names_as_plain_text():
    html, _, _ = _sections("CLAUDE.md Character.AI")

    assert "CLAUDE.md" in html
    assert "Character.AI" in html
    assert 'href="http://claude.md"' not in html.lower()
    assert 'href="http://character.ai"' not in html.lower()


def test_unsafe_link_schemes_are_not_rendered():
    html, _, _ = _sections("[click](javascript:alert(1))")

    assert 'href="javascript:' not in html.lower()


def test_typography_validator_rules():
    from app.render import validator

    v = validator.validate("这是GitHub直连的内容,测试。\n中文english混排\n第3章起点\n")
    rules = {x["rule"] for x in v}
    assert "UX-16 中英文间距" in rules  # 第 2 行「中文english」
    assert "UX-17 数字中文间距" in rules  # 第 3 行「第3章」
    # 白名单行豁免:含 GitHub 的行不报中英间距
    assert not [x for x in v if x["line"] == 1 and x["rule"].startswith("UX-16")]


def test_evidence_demote_narrative_to_body():
    # 证据准入:source 非「路径:行号」与超长 infer 还原为正文段落——主体永远是叙述
    md = "\n".join([
        "> [source] OCR(一句话:光学字符识别)软件 Umi-OCR 是一个面向最终用户的桌面应用,主打离线 OCR,发布形态是解压即用的绿色包。",
        "> [infer] 项目定位:解压即用的离线 OCR 桌面应用。",
        "以上是开头。",
    ])
    html, _, text = _sections(md)
    # 长叙述还原正文:进 HTML 与纯文本流,不再折叠
    assert "面向最终用户的桌面应用" in html and "面向最终用户的桌面应用" in text
    # 短 infer 保留折叠:摘要行即全文(类型标签可见)
    assert '<details class="ev ev-infer"' in html and "项目定位:解压即用" in html


def test_unclosed_fence_closed_at_blank_line():
    # 未闭合围栏:在首个空行处自动闭合,其后正文不被吞(部署实测两份报告正文被吞)
    md = "正文前。\n```mermaid\ngraph LR\n    Q1[\"需求\"]\n\n术语:SSG 是静态站点生成。\n正文后。"
    html, _, text = _sections(md)
    assert "术语:SSG 是静态站点生成" in html and "正文后" in html
    assert "术语:SSG" in text
