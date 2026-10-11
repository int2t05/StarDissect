# round4 修复脚本(逐条 assert):完成后删除
import io

def apply(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, f'MISS {path}: {old[:60]!r}'
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print('ok', path)

# ---- F1:排除仓库不得自动重排 ----
apply('server/app/tasks/queue.py', [
    ('''    if status == "失败" and task["auto_retries"] < config.TASK_AUTO_RETRY_MAX and (network_hit or turn_capped):
        new_limit = min(task["turn_limit"] * 2, config.TASK_TURN_ESCALATE_CAP) if turn_capped else task["turn_limit"]''',
     '''    excluded = conn.execute("SELECT excluded FROM repos WHERE id=?", (task["repo_id"],)).fetchone()
    if status == "失败" and not (excluded and excluded["excluded"]) \\
            and task["auto_retries"] < config.TASK_AUTO_RETRY_MAX and (network_hit or turn_capped):
        new_limit = min(task["turn_limit"] * 2, config.TASK_TURN_ESCALATE_CAP) if turn_capped else task["turn_limit"]'''),
])

# ---- F2:证据块多段 inline 全消费(空行分段不再丢内容) ----
apply('server/app/render/pipeline.py', [
    ('''        inner = [x for x in tokens[i + 1 : j - 1] if x.type == "inline"]
        if inner:
            # 契约:一个证据块一行;连续 > 行会被 lazy continuation 合并,故按行解析,
            # 未命中行保留为普通段落,不丢内容
            divs: list[str] = []
            leftovers: list[str] = []
            for line in inner[0].content.splitlines():''',
     '''        inner = [x for x in tokens[i + 1 : j - 1] if x.type == "inline"]
        if inner:
            # 契约:一个证据块一行;连续 > 行会被 lazy continuation 合并(空行还会拆出
            # 多个 inline),故遍历全部 inline 按行解析,未命中行保留为普通段落,不丢内容
            divs: list[str] = []
            leftovers: list[str] = []
            for x in inner:
              for line in x.content.splitlines():'''),
])

# ---- F3+F4:websearch deep_research 透出错误摘要 ----
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

# ---- B1:硬编码色值/装饰阴影 ----
apply('web/src/views/ReportView.vue', [
    ('#sd-zoom { position: fixed; inset: 0; z-index: 60; background: #000d;', '#sd-zoom { position: fixed; inset: 0; z-index: 60; background: var(--sd-overlay);'),
])
apply('web/src/App.vue', [
    ('.key-echo {\n  position: fixed; left: 20px; bottom: 20px; z-index: 40;\n  background: var(--sd-elevated); color: var(--sd-accent);\n  border: 1px solid var(--sd-border-strong); border-radius: 8px;\n  font-family: var(--sd-font-mono); font-size: 15px; font-weight: 600;\n  padding: 8px 14px; box-shadow: 0 8px 24px #0007;\n}',
     '.key-echo {\n  position: fixed; left: 20px; bottom: 20px; z-index: 40;\n  background: var(--sd-elevated); color: var(--sd-accent);\n  border: 1px solid var(--sd-border-strong); border-radius: 8px;\n  font-family: var(--sd-font-mono); font-size: 15px; font-weight: 600;\n  padding: 8px 14px;\n}'),
])

# ---- C1 + D3(焦点圈闭实现):焦点还原 .zoomable + Tab 圈闭 ----
apply('web/src/views/ReportView.vue', [
    ('''    ov.remove()
    document.querySelector('.article .fig-ok')?.focus?.()''',
     '''    ov.remove()
    document.querySelector('.article .zoomable')?.focus?.()'''),
    ('''  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'Tab') { e.preventDefault(); ov.querySelector('.zoom-close').focus() }  // 焦点圈闭:层内唯一可聚焦元素
  }''',
     '''  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'Tab') { e.preventDefault(); ov.querySelector('.zoom-close').focus() }  // 焦点圈闭:层内唯一可聚焦元素
  }'''),
])

# ---- B2:theme.js 双源维护注记 ----
apply('web/src/theme.js', [
    ('// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60/63),深浅两轴成对,组件零硬编码色值',
     '// Naive UI 主题映射:取值全部源自 UIUX tokens(UX-60/63),深浅两轴成对,组件零硬编码色值\n// 注意:本文件色值与 web/src/styles/tokens.css 成对手工维护——改任一侧必须同步另一侧(UX-55)'),
])

# ---- F3:整形器保护行内 code span(整函数重写为行级状态机) ----
p = 'server/app/render/pipeline.py'
lines = io.open(p, encoding='utf-8').read().splitlines(keepends=True)
start = next(i for i, l in enumerate(lines) if l.startswith('def _normalize_fences'))
end = next(i for i, l in enumerate(lines) if l.startswith('def _quote_mermaid_labels'))
NL = chr(10)
B = chr(92)
T = chr(96) * 3
n = B + 'n'
body = NL.join([
    'def _normalize_fences(md: str) -> str:',
    '    """围栏独立性整形:``` 必须独立成行。修复模型把围栏写进段落句中的情况,',
    '    否则整段被当正文,图/代码块失效。行级处理:反引号成对(行内 code span)的行不动,',
    '    单个行中 ``` 前补空行;开围栏语言标注后同行内容换行;收围栏残留拆行。"""',
    "    langs = '|'.join(_KNOWN_LANGS)",
    '    out = []',
    '    for line in md.split("' + n + '"):',
    '        if line.count("' + T + '") and line.count("' + T + '") % 2 == 0:',
    '            out.append(line)  # 成对行内 code span / 同行开合:不动',
    '            continue',
    f'        line = re.sub(r"(?<!{n}){T}", "{n}{n}{T}", line)  # 行中围栏前补空行',
    f'        line = re.sub(rf"^{T}({langs})[ {B}t]+(?={B}s)", r"{T}{q1}{q2}" + {B} + "n", line)  # 开围栏语言后换行',
    f'        line = re.sub(rf"^{T}[ {B}t]*(?!({langs}){B}b|[ {B}t]*$)([^{B}n]+)$", r"{T}" + {B} + "n" + {q1}{q2}, line)  # 收围栏残留拆行',
    f'        line = re.sub(r"^(?!{T})(.+?){T}[ {B}t]*$", r"{q1}{q2}" + {B} + "n" + r"{T}", line)  # 行中收围栏前置换行',
    '        out.append(line)',
    '    return ' + B + 'n'.join(['chr(10).join(out)']) if False else '    return chr(10).join(out)',
    '',
    '',
])
lines[start:end] = [body]
io.open(p, 'w', encoding='utf-8', newline=NL).write(''.join(lines))
print('pipeline nf rewritten')
