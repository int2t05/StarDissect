# round4 全量修复(Write 工具生成,零转义歧义):完成后删除
import io
import re

def apply(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, f'MISS {path}: {old[:60]!r}'
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print('ok', path)

# ---- F1:排除仓库不得自动重排 ----
apply('server/app/tasks/queue.py', [
    ('''    if status == "失败" and task["auto_retries"] < config.TASK_AUTO_RETRY_MAX and (network_hit or turn_capped):''',
     '''    excluded = conn.execute("SELECT excluded FROM repos WHERE id=?", (task["repo_id"],)).fetchone()
    if status == "失败" and not (excluded and excluded["excluded"]) \\
            and task["auto_retries"] < config.TASK_AUTO_RETRY_MAX and (network_hit or turn_capped):'''),
])

# ---- F2:证据块多段 inline 全消费 ----
apply('server/app/render/pipeline.py', [
    ('''            divs: list[str] = []
            leftovers: list[str] = []
            for line in inner[0].content.splitlines():''',
     '''            divs: list[str] = []
            leftovers: list[str] = []
            for x in inner:
              for line in x.content.splitlines():'''),
])

# ---- F4:deep_research 透出后端故障摘要 ----
apply('server/app/agents/websearch.py', [
    ('''    results = await chain.search(query, min(max_pages, config.MAX_DEEP_PAGES))
    if not results:
        return "无搜索结果"''',
     '''    results = await chain.search(query, min(max_pages, config.MAX_DEEP_PAGES))
    if not results:
        if chain.last_errors:
            return "无搜索结果(后端故障: " + "; ".join(chain.last_errors) + ")"
        return "无搜索结果"'''),
])

# ---- B1:硬编码色值 / 装饰阴影 ----
apply('web/src/views/ReportView.vue', [
    ('#sd-zoom { position: fixed; inset: 0; z-index: 60; background: #000d;',
     '#sd-zoom { position: fixed; inset: 0; z-index: 60; background: var(--sd-overlay);'),
])
apply('web/src/App.vue', [
    ('  padding: 8px 14px; box-shadow: 0 8px 24px #0007;',
     '  padding: 8px 14px;'),
])

# ---- B2:theme.js 双源维护注记 ----
apply('web/src/theme.js', [
    ('// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60/63),深浅两轴成对,组件零硬编码色值',
     '''// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60/63),深浅两轴成对,组件零硬编码色值
// 注意:本文件色值与 web/src/styles/tokens.css 成对手工维护——改任一侧必须同步另一侧(UX-55)'''),
])

# ---- C1:焦点还原目标修正 + 焦点圈闭(Tab 留在层内) ----
apply('web/src/views/ReportView.vue', [
    ('''    ov.remove()
    document.querySelector('.article .fig-ok')?.focus?.()''',
     '''    ov.remove()
    document.querySelector('.article .zoomable')?.focus?.()'''),
    ('''  const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close() } }''',
     '''  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'Tab') { e.preventDefault(); ov.querySelector('.zoom-close').focus() }  // 焦点圈闭:层内唯一可聚焦元素
  }'''),
])
print('part1 done')

# ---- F3:_normalize_fences 重写(split 法,无反斜杠歧义;行内 code span 保护) ----
p = 'server/app/render/pipeline.py'
s = io.open(p, encoding='utf-8').read()
start = s.index('def _normalize_fences')
end = s.index('def _quote_mermaid_labels')
new_fn = '''def _normalize_fences(md: str) -> str:
    """围栏独立性整形:``` 必须独立成行。修复模型把围栏写进段落句中的情况。
    按 ``` 分段重组:仅当存在「语言标注后同行接内容」的粘连特征才整形;
    反引号成对的行内 code span 不受影响。"""
    if md.count("```") < 2:
        return md
    parts = md.split("```")
    glued = any(
        re.match(r"^([A-Za-z0-9_#+-]+)[ \\t]+\\S", seg)
        and seg.split(" ")[0].strip() in set(_KNOWN_LANGS)
        for i, seg in enumerate(parts)
        if i % 2 == 1
    )
    if not glued:
        return md
    out = [parts[0].rstrip()]
    for i, seg in enumerate(parts[1:], 1):
        if i % 2 == 1:  # 围栏内部:语言标注与同行内容拆行
            seg = re.sub(r"^([A-Za-z0-9_#+-]+)[ \\t]+(?=\\S)", r"\\1\\n", seg, count=1)
            out.append("\\n\\n" + seg.rstrip())
        else:  # 围栏外文本:前后留空行
            out.append("\\n\\n" + seg.lstrip("\\n"))
    return "```".join(out)


'''
s = s[:start] + new_fn + s[end:]
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('pipeline normalize rewritten')

# ---- D 组文档同步 ----
apply('docs/v1.0/tech.md', [
    ('- 网络类失败自愈(工程补强):失败原因命中 clone/模型网关类标记且 auto_retries 未达上限时,自动重排同任务(优先级排新 star 之后);人工重试不受此限。',
     '''- 失败自愈(工程补强):网络类失败(clone/模型网关)按原预算自动重排,轮次上限失败按预算加倍(封顶 TASK_TURN_ESCALATE_CAP)重排一次,均以 auto_retries 计数、上限 3 次;排除仓库不重排;人工重试不受此限。'''),
    ('      auto_retries,                                -- 网络类失败自动重排计数(上限 TASK_AUTO_RETRY_MAX)',
     '      auto_retries,                                -- 失败自动重排计数(网络类/轮次预算加倍,上限 TASK_AUTO_RETRY_MAX)'),
])
s = io.open('docs/v1.0/tech.md', encoding='utf-8').read()
anchor = '2. markdown-it-py 解析 → token 流:渲染器把上述引用块转为 UIUX §8 结构;```mermaid fence 由专用渲染规则输出 `<div class="mermaid">` 容器(前端渲染+文字后备)。'
assert anchor in s
s = s.replace(anchor, '''1a. 围栏整形 `_normalize_fences`:把写进段落句中的 ``` 块整形为独立围栏(修复 agent 粘连输出);
1b. mermaid 标签规范化 `_quote_mermaid_labels`:未引号节点标签补双引号(标签含 {} 必解析失败);
2. markdown-it-py 解析 → token 流:渲染器把上述引用块转为 UIUX §8 折叠结构;```mermaid fence 由专用渲染规则输出 `<div class="mermaid">` 容器(前端渲染+文字后备)。前端 ReportView 内置同源修复规则作最后兜底。''')
io.open('docs/v1.0/tech.md', 'w', encoding='utf-8', newline='\n').write(s)
print('tech done')

apply('docs/uiux/UIUX.md', [
    ('| UX-61 | 布局范式:顶栏 + 居中内容 | VitePress/Linear 式吸顶顶栏;内容列居中占主体;文章页大纲右浮(≥1366px,auto-trend 风格:本页大纲标题/hairline/主色指示);页面容器统一 .page(8 基数纵向间距) |',
     '''| UX-61 | 布局范式:顶栏 + 居中内容 | VitePress/Linear 式吸顶顶栏;阅读页三列:左侧工作区面板(报告信息/阅读状态/排版调节/进度导出,sticky)+ 居中正文 + 大纲右浮(≥1366px,auto-trend 风格);页面容器统一 .page(8 基数纵向间距) |'''),
    ('| UX-48 | 图表与表格 | mermaid 渲染区 + 图题 + 放大层(滚轮缩放、Esc 退出、焦点圈闭) + 文字后备折叠;宽表格容器内滚动,页面不横向溢出 |',
     '| UX-48 | 图表与表格 | mermaid 渲染区 + 图题 + 放大层(滚轮缩放、拖拽平移、Esc 退出、焦点圈闭已实现) + 文字后备折叠;宽表格容器内滚动,页面不横向溢出 |'),
])
print('uiux done')
