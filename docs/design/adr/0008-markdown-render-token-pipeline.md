# ADR-0008 Markdown 服务端渲染:markdown-it-py token 流管线

状态:草案 · 2026-10-09

## 背景

报告正文由 agent 以 Markdown 产出;消费方有四:阅读 HTML(REQ-READ-001)、中文排版校验(REQ-RPT-003/UX-16…20,跳过代码块与行内代码)、搜索索引(ADR-0006)、目录/锚点(ADR-0007)。前端不做渲染逻辑(UIUX §11 UX-57)。

## 决策

markdown-it-py(commonmark+table/strikethrough 等有限插件)服务端渲染:一次解析得 token 流,token 流同时派生 1) 最终 HTML(证据标注语法→UX-43…47 结构);2) 纯文本章节流(跳过 code_block/inline code 的 fence 区段,供排版校验);3) 章节+行号 map(供 ADR-0006/0007)。HTML 与章节链存 report_versions,阅读页零渲染。

## 理由与落选

- 前端渲染(markdown-it 浏览器版):四消费方仍需服务端重做解析,双份逻辑必然漂移。落选。
- mistune/markdown-py:token 流开放性与插件生态不及 markdown-it 系;UIUX 既有依据链(VitePress 同源生态)亦指向 markdown-it。落选。
- markdown-it token `map` 行号能力已核验(reference/markdown-it-py/docs/using.md:229,查阅 2026-10-09);代码高亮用 pygments 挂 renderer(参考 pygments,查阅 2026-10-09)。

## 影响

证据块语法(agent 产出约定)与渲染器一一对应,是 agent 提示词与校验器的共同契约(细化见 v1.0/tech.md 渲染管线节);UIUX.md 中「校验输入用 ADR-0008 的 token 流」的引用自此闭合。

## 参考

- reference/markdown-it-py/docs/using.md:229(查阅 2026-10-09):Token 构造与 map 行区间。
- reference/pygments/(查阅 2026-10-09):服务端代码高亮。
- reference/vitepress/(查阅 2026-10-09):markdown-it 生态内「token→目录/搜索」的完整先例。
