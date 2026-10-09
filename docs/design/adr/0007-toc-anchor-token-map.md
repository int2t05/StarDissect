# ADR-0007 目录锚点与命中回源:token map 行号

状态:草案 · 2026-10-09

## 背景

三个消费方依赖同一份章节结构:阅读页目录与 scrollspy(REQ-READ-002/UX-59)、搜索命中按「报告>章节」分组并回源(REQ-SRCH-001/UX-41)、阅读进度锚点(REQ-READ-003/UX-26)。

## 决策

以 ADR-0008 token 流为唯一结构源:渲染期提取 h2/h3 token,由其 `map` 行号生成章节链(层级标题模型同 VitePress `title/titles`),连同 HTML 一并存库;章节锚点=`v{版本}-s{序}`;搜索命中携带章节链与正文偏移,回源到「报告>章节」;进度锚点即章节序+段落索引。

## 理由与落选

- 渲染后从 HTML 反解析标题:二次解析、无行号、三处消费各自为政。落选。
- markdown-it token 的 `map` 原生携带行区间(`Token("heading_open",..., map=[n, m])`,reference/markdown-it-py/docs/using.md:229,查阅 2026-10-09),一行不差地支撑锚点与回源——零额外标注成本,这是本方案的决定性证据。

## 影响

UIUX.md 中「ADR-0008 token map 提供」「map 行号用于目录树与命中片段回源」两处引用,指向本 ADR 与 ADR-0008;scrollspy 算法本体仍以 UX-59(改写 VitePress outline)为准,本 ADR 只供数据。

## 参考

- reference/markdown-it-py/docs/using.md:229(查阅 2026-10-09):token.map 行区间证据。
- reference/vitepress/src/client/theme-default/composables/outline.ts:79-221(查阅 2026-10-09):title/titles 层级模型与判定算法(实现按 UX-59 改写)。
