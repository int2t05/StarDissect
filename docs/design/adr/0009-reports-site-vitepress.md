# ADR-0009 报告阅读面迁 VitePress 静态站:SPA 瘦身为管理面

状态:已采纳 · 2026-11-05

## 背景

报告阅读页(REQ-READ-001)长期由 SPA 的 ReportView 承担:服务端预渲染 HTML 落库,前端做 DOM 手术
(证据折叠合并、mermaid 渲染、放大层、进度上报),无代码高亮;管理面(同步/分类/队列/设置)与
阅读面耦合在同一 SPA 里。同时个人另有 FluxSift 阅读站已迁 VitePress 1.6(github-light/dark
Shiki、本地搜索、深浅色),两站阅读体验不统一是直接动因。

## 决策

新建 `reports-site/`(VitePress,版本钉死 1.6.4,与 FluxSift 同版本同 Shiki 主题):
`base=/reports/`,由 `server/app/site.py` 从 `report_versions`(未归档)整树导出
`src/<full_name 换 __>/<vid>/index.md`(frontmatter:repo/version/commit/generated_at/vid),
正文经 `_normalize_fences` 预整形;FastAPI 在 `/api` 路由后、SPA 前以 StaticFiles 挂
`/reports`。SPA 删除 ReportView 与 scrollspy/进度 composables,报告链接改为整页跳转静态站;
SPA 保留 useReaderSettings(全局主题)与全部管理面。阅读交互移植到 VitePress 主题层:

- **JS 插件**(与 Python 管线同源移植,ADR-0008 契约不变):证据块 blockquote → `details.ev`
  (含 `data-refs`,准入 `_REF_SHAPE`/`_DEMOTE_CHARS` 一致);mermaid fence → 专用容器;
  h2/h3 → `id=sec-N` + `data-seq`(进度/scrollspy 消费契约)。
- **ReportShell/ReportToolbar/ReadState/ProgressTracker/ReaderSettings**:证据合并、
  GitHub 源码链接(锚定 commit)、mermaid 渲染+放大层、已读/收藏(PATCH state)、
  高水位进度(PUT progress 契约不变)、字号/行宽/行高/强对比(localStorage 改用
  `reports-` 前缀);目录由 VitePress outline 原生接管。
- **双向导航**：SPA 顶栏可进入 `/reports/`；报告站导航直达 SPA 的阅读中心、仓库库、分析管理与系统设置，迁移阅读面不替换管理功能。

服务端管线(ADR-0008)**原样保留**:章节提取、排版校验、FTS、RSS、`/reports/{vid}/export`
都消费它,渲染逻辑不双写——站点插件只服务阅读站的呈现层。重建走 daemon 线程
(dirty + 单工人),触发点:分析任务落库、报告删除、`POST /api/site/rebuild`;
`STARDISSECT_SITE_REBUILD=0` 关停(测试缝);构建日志在 `data/logs/site-build.log`,
构建前清空 dist。

## 理由与落选

- **保留 SPA 阅读页**:三代形态的 DOM 手术复杂度已到顶,无高亮、无搜索、无深浅色与 FluxSift
  统一的可能;继续投入是在沉没成本上加功能。落选。
- **SSR/服务端继续全量渲染 HTML 供静态站用**:静态站要 VitePress 的导航/搜索/主题,吃的是
  Markdown 源而非 HTML;预渲染 HTML 反而要二次加工。落选。
- **报告站并入 SPA(naive-ui 化)**:等于重写一个 VitePress。落选。

## 影响

- 阅读链接从 `/repos/<id>/report/<vid>`(hash 路由内)变为 `/reports/<full_name 换 __>/<vid>/`
  的整页跳转;RSS item link 同步换轨,**guid 不变**,订阅端不重复推送。
- 部署多一步 node/npm(reports-site `npm ci && npm run build`,deploy.sh 已含);缺失时报告站
  404,管理面与 API 不受影响。
- 证据块/mermaid/锚点契约现在是「提示词 ↔ 服务端管线 ↔ 站点插件」三方同步,改动须三处同改。
- 旧进度数据(reading_progress)无缝沿用:report_version_id 与 anchor 语义未变。

## 参考

- reports-site/.vitepress/theme/plugins/(与 server/app/render/pipeline.py 的对照)
- FluxSift 仓库 site/(同版本脚手架的先例,2026-11-05)
