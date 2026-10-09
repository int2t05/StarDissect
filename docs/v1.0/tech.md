# TECH v1.0 — StarDissect 星剖 实现蓝图

<!-- v1.0 实现依据:结构、数据模型、agent 规格、渲染契约、API 面。上层见 docs/TECH.md 与 ADR-0001…0008;需求见 docs/v1.0/prd.md。 -->

| 项   | 值                                 | 项     | 值                                        |
| ---- | ---------------------------------- | ------ | ----------------------------------------- |
| 版本 | v1.0(2026-10-09)                   | 状态   | 草案(待人工审计)                          |
| 依据 | ADR-0001…0008 · UIUX 定稿 · PRD v1.0 | 审计  | docs/TECH.md §AUD                         |

## 1. 目录结构

```text
server/                     # 单进程 FastAPI 应用(ADR-0001)
  app/
    main.py                 # 应用装配:路由挂载、静态托管、调度与队列启动
    config.py               # 环境与路径配置
    db.py                   # SQLite 连接(WAL)、schema 迁移
    models.py               # Pydantic 模型(表行与 API 契约共用)
    sync/                   # 同步器(ADR-0003)
    tasks/                  # 队列与状态机(ADR-0004)
    agents/                 # classifier / analyzer 及工具集(ADR-0005)
    render/                 # 渲染管线(ADR-0008)
    search/                 # 分词与索引(ADR-0006)
    api/                    # REST 路由(§6)
  tests → ../test           # 测试入口
web/                        # Vue 3 SPA(UIUX §11 结构:tokens/组件树/composables)
test/                       # 测试(真实调用,无 mock,见 §8)
data/                       # 运行产物:app.db、仓库克隆克隆区(不入库)
docs/                       # 本文档体系
```

## 2. 数据模型(DDL 要点;约束=REQ/RPT-004 只增不覆、CLS-003/005 写入隔离)

```sql
repos(id PK, github_id UNIQUE, full_name, description, language, default_branch,
      head_commit, status,            -- PRD FIG-02 状态
      excluded INT DEFAULT 0, unstarred INT DEFAULT 0,
      starred_at, created_at, updated_at)

classifications(id PK, repo_id FK, type, reason, confidence,   -- 高/中/低
      source,               -- auto / deep / manual_lock / manual_scope
      locked INT DEFAULT 0, created_at)
classification_history(id PK, repo_id FK, old_type, new_type, reason, created_at)

tags(id PK, repo_id FK, name, created_at)          -- 仅人工写入(REQ-CLS-005)

tasks(id PK, repo_id FK, kind,                     -- analyze / reanalyze
      status,                                      -- 排队/进行/完成/受限完成/失败/中断
      priority, turn_limit, time_limit_sec,        -- 入队时快照(REQ-CFG-002)
      started_at, finished_at, fail_reason)

report_versions(id PK, repo_id FK, version_no, task_id FK,
      commit_anchor, markdown, html, sections_json,   -- markdown=导出原文(REQ-OUT-001)
      meta_json, read, favorited,                     -- 条目级已读/收藏(REQ-READ-006)
      created_at, UNIQUE(repo_id, version_no))

knowledge_points(id PK, repo_id FK, report_version_id FK,
      statement, evidence_json,                    -- 结论+证据引用(KP-001)
      human_edited INT DEFAULT 0, revision_note, deleted INT DEFAULT 0)

reading_progress(report_version_id PK, anchor, top_percent, bottom_percent,
      highest_anchor, updated_at)                  -- UX-26…28,高水位写入

sync_runs(id PK, started_at, finished_at, added, removed, skipped, failed, cursor)

settings(key PK, value)                            -- token/密钥/限额;API 永不回显明文

report_sections(id PK, report_version_id FK, seq, title, path_chain, text_content)
report_fts(fts5, 自持分词副本)                      -- snippet 取自索引副本(ADR-0006 修订)
knowledge_fts(fts5, 自持分词副本)                    -- 知识点检索域(REQ-SRCH-001)
repo_fts(fts5, 自持分词副本)                         -- 仓库元信息检索域(REQ-SRCH-001)
```

人工数据隔离:tags 表无自动写路径;classifications 的 `locked=1` 行由应用层在 agent 落库前拦截;knowledge_points 的修订走 human_edited 痕迹(AUD-07 关闭点)。

## 3. 任务与队列语义(ADR-0004;状态机=PRD FIG-02)

- 工作循环:取最高优先级「排队」任务 → 置「进行」(写 turn/time 快照)→ 执行 ADR-0005 agent → 按结果落「完成/受限完成/失败」;每步单事务提交。
- 干预(REQ-TASK-002):暂停/恢复=循环开关;优先级/取消/排除=tasks/repos 字段更新;「分析中」终止=触发 asyncio 取消→归「失败」(可重试)。
- 限额(REQ-TASK-003):request_limit 与墙钟超时双约束;超限后若 report_versions 已有完整新版本→「受限完成」保留产出,否则「失败」。
- 重试/重分析(REQ-TASK-004/005):新增 tasks 行,不覆盖历史;同仓库「进行」存在则拒绝。
- 启动恢复(REQ-TASK-006):扫描「进行」→置「中断」;产出的半成品由事务原子性保证不存在。

## 4. 分析 agent 规格(ADR-0005)

**输入上下文**:仓库浅克隆到 `data/clones/<repo>/` 并检出 head_commit(即 commit_anchor);README、元数据、目录树随 prompt 注入。

**工具集**(作用域限克隆目录与 GitHub 只读):

| 工具            | 语义                                   | 证据去向            |
| --------------- | -------------------------------------- | ------------------- |
| read_file       | 路径+行区间                            | 源码事实(路径:行号) |
| search_code     | 正则/文本搜索克隆区                    | 源码事实             |
| list_dir        | 目录树                                 | —                    |
| fetch_github    | README/Issue/PR 只读                   | 作者说明/外部背景     |
| web_search      | 网络搜索,降级链 Tavily→Exa→DuckDuckGo(参考 Cognik SearchChain);片段是线索非证据 | 外部背景(引用前须 web_fetch 核实) |
| deep_research   | 深度调研:搜索+前 N 页正文蒸馏,单次调用完成多源收集(参考 gpt-researcher 模式) | 外部背景 |
| web_fetch       | 作者文档/外部资料                      | 外部背景(带查阅时间) |

**classifier**:一次调用(README+树)→ `{type, reason, confidence}`;锁定仓库跳过。

**analyzer**:多步循环 → `ReportDraft{sections[](含证据标注语法), knowledge_points[], classification_correction?}`。修正仅在非锁定时落库并写 classification_history(REQ-CLS-004)。提示词包含:七类模板(项目 PRD 表)、证据五类定义、报告正文中文要求、未知须明示(REQ-RPT-002/003)。

**产物落库**:ReportDraft → 渲染管线(§5)→ report_versions+report_sections(单事务)+ 知识点 → FTS 索引 → RSS 条目生成(REQ-OUT-002)。

## 5. 渲染管线(ADR-0008;契约级约定)

1. agent 产出的证据块语法(共同契约,提示词与渲染器同步维护):
   - `> [source] path:line` → 源码事实引用块(UX-43)
   - `> [author] 文本 (url, 日期)` → 作者说明(UX-44)
   - `> [infer] 文本` → 分析推断(UX-45)
   - `> [external] 文本 (url, 日期)` → 外部背景(UX-46)
   - `> [unknown] 文本` → 未知/冲突提示条(UX-47)
2. markdown-it-py 解析 → token 流:渲染器把上述引用块转为 UIUX §8 结构;pygments 高亮。
3. 同一 token 流派生:h2/h3 章节+`map` 行号链(ADR-0007)→ sections_json;跳过代码区段的纯文本 → report_sections.text_content(校验输入与 FTS 索引共用)。
4. 排版校验(REQ-RPT-003):UIUX-16…20 规则作用于纯文本流,违规记录入 meta_json(标记不阻断,→OPN-04)。

## 6. API 面(REST,`/api` 前缀;SPA 由同进程静态托管)

| 端点                            | 方法           | 覆盖 REQ                |
| ------------------------------- | -------------- | ----------------------- |
| /api/sync                       | POST/GET 状态  | SYNC-001/002/003        |
| /api/repos                      | GET(筛选/标签) | CLS-005、TASK-001       |
| /api/repos/{id}                 | GET/PATCH      | CLS-001…005、TASK-002 排除 |
| /api/repos/{id}/analyze         | POST           | TASK-005                |
| /api/tasks                      | GET/PATCH/POST | TASK-001…004            |
| /api/tasks/{id}                 | DELETE         | TASK-002(按 id 取消排队)|
| /api/tasks/{id}/terminate       | POST           | TASK-002(终止分析中)    |
| /api/reports/{vid}/state        | PATCH          | READ-006(已读/收藏)    |
| /api/knowledge_points/{id}      | PATCH/DELETE   | KP-002(人工修订/软删除) |
| /api/repos/{id}/reports         | GET(版本列表)  | RPT-004、TASK-005       |
| /api/reports/{version_id}       | GET(html/sections) | READ-001…005        |
| /api/reports/{version_id}/progress | PUT/GET     | READ-003                |
| /api/search                     | GET(q=)        | SRCH-001/002            |
| /api/reports/{version_id}/export | GET(.md)     | OUT-001                 |
| /rss.xml                        | GET            | OUT-002                 |
| /api/settings                   | GET/PATCH      | CFG-001/002(密钥仅尾号) |

## 7. 部署形态

单命令启动(uvicorn 单 worker + 前端构建产物);首次运行建库/迁移;外网暴露由部署者反代保护(DEC-04/OPN-08);RSS 地址供本人阅读器添加(REQ-OUT-002)。

## 8. 测试策略(test/,真实调用无 mock)

- 单元:分词、渲染管线(证据块→结构、map 行号)、限额归档逻辑、高水位进度写入。
- 集成:SQLite 全链路(同步模拟数据→分类→任务→渲染→检索→导出);GitHub/LLM 走真实接口,依赖 settings 密钥,无密钥环境的用例显式跳过并标注。
- 验收:AC-001…028 逐条映射用例;UIUX 断点(NFR-05)手测记录归 AUD-10。
