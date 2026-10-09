# round3 修复续(剩余项):完成后删除
import io
import re

def apply(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, f'MISS {path}: {old[:60]!r}'
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print('ok', path)

apply('web/src/styles/tokens.css', [
    ('/* 排版(UX-09/UX-10 修订):三档行宽 68/80/96,默认标准 80ch;间距 8 基数(UX-07) */',
     '/* 排版(UX-09/UX-10):三档行宽 72/84/100,默认标准 84ch;间距 8 基数(UX-07) */'),
])

# docs:tech.md 五处
apply('docs/v1.0/tech.md', [
    # D1: classifier 输出补 tags
    ('**classifier**:一次调用(README+树)→ `{type, reason, confidence}`;锁定仓库跳过。',
     '**classifier**:一次调用(README+树)→ `{type, reason, confidence, tags[2-4]}`;tags 写 auto_tags 并入检索域;锁定仓库跳过分类。'),
    # D2: kp restore 入表
    ('| /api/knowledge_points/{id}      | PATCH/DELETE   | KP-002(人工修订/软删除) |',
     '''| /api/knowledge_points/{id}      | PATCH/DELETE   | KP-002(人工修订/软删除) |
| /api/knowledge_points/{id}/restore | POST        | KP-002(软删除恢复)      |'''),
    # D9: 排队/进行均拒
    ('- 重试/重分析(REQ-TASK-004/005):新增 tasks 行,不覆盖历史;同仓库「进行」存在则拒绝。',
     '- 重试/重分析(REQ-TASK-004/005):新增 tasks 行,不覆盖历史;同仓库「排队/进行」存在则拒绝。'),
    # D3: §8 措辞
    ('- 验收:AC-001…028 逐条映射用例;UIUX 断点(NFR-05)手测记录归 AUD-10。',
     '- 验收:AC 验收映射由审计台账(docs/audit/)追踪;UIUX 断点(NFR-05)手测记录归审计。'),
    # §2: tags UNIQUE + auto_tags 已在? 补 tags UNIQUE 与迁移边界
    ('tags(id PK, repo_id FK, name, created_at)          -- 仅人工写入(REQ-CLS-005)',
     'tags(id PK, repo_id FK, name, created_at, UNIQUE(repo_id,name))  -- 仅人工写入(REQ-CLS-005)'),
])
s = io.open('docs/v1.0/tech.md', encoding='utf-8').read()
if '迁移=幂等重放' not in s:
    s = s.replace('settings(key PK, value)                            -- token/密钥/限额;API 永不回显明文',
                  'settings(key PK, value)                            -- token/密钥/限额;API 永不回显明文\n\n# 迁移机制:PRAGMA user_version + SCHEMA 幂等重放(IF NOT EXISTS);不支持既有表的列变更,结构性变更需重建路径')
    io.open('docs/v1.0/tech.md', 'w', encoding='utf-8', newline='\n').write(s)
print('tech done')

# prd: 检索域措辞 + FIG-02 补中断
apply('docs/v1.0/prd.md', [
    ('- 行为:检索范围=报告全文+知识点+仓库元信息(名称/描述/人工标签);',
     '- 行为:检索范围=报告全文+知识点+仓库元信息(名称/描述/人工+自动标签);'),
    ('''  分析中 --> 可阅读: 生成新报告版本
  分析中 --> 失败: 出错·超限·服务中断·人工终止
  失败 --> 排队中: 手动重试''',
     '''  分析中 --> 可阅读: 生成新报告版本
  分析中 --> 失败: 出错·超限·人工终止
  分析中 --> 中断: 服务重启
  中断 --> 排队中: 手动重试
  失败 --> 排队中: 手动重试'''),
])
# 分类服务不可用→改述(C8)
apply('docs/v1.0/prd.md', [
    ('- 异常:分类服务不可用→仓库停留「已收录」,下轮自动重试。',
     '- 异常:分类失败→仓库停留「已收录」,可在仓库库重新触发。'),
])
print('prd done')

# UIUX: A1/A2/D4/D8 + 编号归位
p = 'docs/uiux/UIUX.md'
s = io.open(p, encoding='utf-8').read()
# 1) 从 §1 删除 UX-60/61(移至 §11 尾)
m60 = re.search(r'\| UX-60 \|[^\n]*\n', s)
m61 = re.search(r'\| UX-61 \|[^\n]*\n', s)
assert m60 and m61
line60, line61 = m60.group(0), m61.group(1) if False else m61.group(0)
s = s.replace(line60, '').replace(line61, '')
# 2) UX-27 已修订措辞去「(UX-61 修订)」
s = s.replace('**进入文章默认开头**，恢复经「继续上次」显式触发（UX-61 修订）',
              '**进入文章默认开头**，恢复经「继续上次」显式触发')
# 3) UX-10 去修订/实测叙事
s = s.replace('| UX-10 | 行宽   | 标准 84ch（窄 72 / 宽 100 三档；UX-61 重构修订，文章居中占主体）                          | PRD REQ-READ-001 宽度可调；档位经部署阅读体验校准                                     |',
              '| UX-10 | 行宽   | 标准 84ch（窄 72 / 宽 100 三档；文章居中占主体）                                        | PRD REQ-READ-001 宽度可调；档位为 UX-61 定稿                                          |')
# 4) UX-31 档位对齐
assert '62/72/88ch' in s
s = s.replace('62/72/88ch', '72/84/100ch')
# 5) UX-22 目录 200px 对齐实现
s = s.replace('右目录 240px（钉右侧视口边缘）', '右目录 200px（钉右侧视口边缘）')
# 6) §11 尾(UX-59 行后)追加 60/61/62
anchor = re.search(r'(\| UX-59 \|[^\n]*\n)', s)
assert anchor
addition = ('| UX-60 | 组件库 Naive UI | 主题经 n-config-provider themeOverrides 完全映射本规范 tokens（web/src/theme.js），深浅两轴成对；组件零硬编码色值原则不变                                                          |\n'
            '| UX-61 | 布局范式：顶栏 + 居中内容 | VitePress/Linear 式吸顶顶栏；内容列居中占主体；文章页大纲右浮（≥1366px，auto-trend 风格：本页大纲标题/hairline/主色指示）；页面容器统一 .page（8 基数纵向间距） |\n'
            '| UX-62 | 标签双轨展示 | 仓库抽屉「标签」区:自动标签 info 芯片（AI 分类生成,auto_tags）与人工标签分区显示;自动标签入检索域 |')
s = s.replace(anchor.group(1), anchor.group(1) + addition)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('uiux done')

# websearch 措辞:去「唯一陈述」
apply('server/app/agents/websearch.py', [
    ('# 顺序降级 Tavily→Exa→DuckDuckGo,首个成功即返回;「线索≠证据」纪律的唯一陈述见 docs/v1.0/tech.md §4',
     '# 顺序降级 Tavily→Exa→DuckDuckGo,首个成功即返回;「线索≠证据」纪律的契约见 docs/v1.0/tech.md §4'),
])
apply('.env.example', [
    ('# 深度搜索工具链(agent 的 web_search 降级链:Exa→Tavily→DuckDuckGo;后者无需 key)',
     '# 深度搜索工具链(agent 的 web_search 降级链:Tavily→Exa→DuckDuckGo;后者无需 key)'),
])
# index.html 接线 32px png(C9)
apply('web/index.html', [
    ('    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />',
     '''    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="icon" href="/favicon-32.png" type="image/png" sizes="32x32" />'''),
])
print('ALL DONE')
