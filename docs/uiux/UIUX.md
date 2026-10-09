# UIUX — 前端设计定稿（夜航 · 开发者深色）

> 视觉方向 **C 夜航**（[mockups/style-c-nocturne.html](mockups/style-c-nocturne.html)）；产品图标 **A 解剖星**（[icons/icon-a-dissected-star.svg](icons/icon-a-dissected-star.svg)）。本文是实现依据：tokens、排版、交互、组件规格，每项关键选择标注来源依据（`reference/<仓库>/<路径>`）。
> 备选方向（style-a/style-b、icon-b/c/d）为落选存档，仅供回溯。
> 编号约定：本文规则 ID（UX-xx）全文档顺序编号；全库 ID 体系见 TECH 头部约定行。

## 1. 设计原则

| ID    | 原则                               | 内容                                                                                                                                              |
| ----- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-01 | 灰阶主体 + 单一强调色 + 状态聚焦   | 与 miniflux 深色主题同构（`reference/miniflux/internal/ui/static/css/dark.css`：低饱和灰阶正文、唯一蓝强调只用于焦点/当前项）；夜航的琥珀 `--sd-accent` 收敛为三个用途：焦点态、当前项、激活态 |
| UX-02 | 内容优先                           | 阅读页一等公民；管理页允许工具化密度                                                                                                              |
| UX-03 | 证据可见                           | 事实/作者说明/推断/未知的区分用「图标+文字标签+结构差异」表达，不依赖颜色（PRD REQ-RPT-002）                                                             |
| UX-04 | 双轴正交                           | 明暗轴（浅/深/跟随系统）×字体轴（无衬线/衬线）互相独立，同 miniflux 的 6 bundle 模型（`internal/ui/static/static.go`）；夜航以深色为第一公民，浅色轴同 tokens 成对补齐 |
| UX-05 | 键盘可达                           | miniflux 式键盘模型（§7）                                                                                                                         |

## 2. 设计 tokens

```css
/* 深色（默认）——来自 mockup，实现照抄 */
--sd-bg:#101014; --sd-surface:#18181f; --sd-elevated:#20202a;
--sd-border:#2b2b36; --sd-border-strong:#3d3d4c;
--sd-text:#e9e9ee; --sd-text-2:#a3a3b3; --sd-text-3:#6e6e80;
--sd-accent:#e8a33d; --sd-accent-soft:#e8a33d1c;
--sd-focus:#e8a33d88;          /* 焦点外圈，用法对照 miniflux focus-box-shadow */
--sd-ev-source:#4ade80; --sd-ev-author:#67b7ff; --sd-ev-infer:#e8a33d;
--sd-ev-external:#c4a5ff; --sd-ev-unknown:#7a7a8c;
/* 浅色轴成对定义（同一变量名换值），html 加 color-scheme:dark|light
   （miniflux dark.css 对 color-scheme 的用法），字体轴仅换 --sd-font-* 两个变量 */
```

| ID    | 项   | 规定                                                                                                                                                    |
| ----- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-06 | 字体 | 正文/标题 `-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",system-ui`；等宽 `ui-monospace,"Cascadia Code","JetBrains Mono",Consolas`；衬线轴（可选扩展）：`Georgia,"Songti SC","Noto Serif SC",serif` |
| UX-07 | 刻度 | 间距 4 基数（4/8/12/16/24/32/48/64）；圆角 6px（surface）+ 4px（inline）；阴影只用于悬浮层（`--sd-glow`）                                                |
| UX-08 | 动效 | 遵循 `prefers-reduced-motion`（miniflux `common.css` 同款降级），焦点环永远瞬时                                                                          |

## 3. 排版规格（阅读正文）

| ID    | 项     | 值                                                                                      | 依据                                                                        |
| ----- | ------ | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| UX-09 | 正文   | 15.5px / 行高 1.8 / `overflow-wrap:break-word`                                          | 中文长文比 miniflux（1.2em/1.4）更疏朗；break-word 同 miniflux `common.css` |
| UX-10 | 行宽   | 标准 84ch（窄 72 / 宽 100 三档；文章居中占主体）                          | PRD REQ-READ-001 宽度可调；档位为 UX-61 定稿                                     |
| UX-11 | 标题   | h2 19px / h3 16px，上方 20px 分隔线                                                     | mockup                                                                      |
| UX-12 | 引用块 | 左侧 3px 强调线，**字族复用正文字体变量** `--sd-font-body`                              | miniflux `--entry-content-quote-font-family` 模式（`common.css:1179-1187`） |
| UX-13 | 代码块 | 深底 `#0c0c10`、独立等宽族、可横向滚动、颜色走变量                                      | miniflux pre 三变量模式（`common.css:1203-1216`）                           |
| UX-14 | 图     | `max-width:100%`；figure 1px 边框 + figcaption 0.75em 小字距大写英文标签可换小号中文    | miniflux figure/figcaption（`common.css:1121-1148`）                        |
| UX-15 | 长列表 | 列表项 `content-visibility:auto; contain-intrinsic-size:auto 100px`                     | miniflux 列表性能细节（`common.css:831-835`）                               |

### 中文排版硬性规范（进入报告校验器）

来自 [中文文案排版指北](../../reference/chinese-copywriting-guidelines/)，高置信规则进 quality 校验器（低置信/语义类仅写入模板提示词），全部支持白名单例外（产品名官方拼写等）；校验输入用 ADR-0008 的 token 流，**跳过代码块与行内代码**：

| ID    | 规则                                                         | 校验方式                       |
| ----- | ------------------------------------------------------------ | ------------------------------ |
| UX-16 | 中英文/中文与数字之间加空格                                   | 正则 `[一-龥][A-Za-z0-9_]` 及反向 |
| UX-17 | 数字与单位间空格；`°`/`%` 例外不加                            | 单位白名单 + 例外正则          |
| UX-18 | 全角标点两侧不加空格；标点不重复                              | 正则                           |
| UX-19 | 中文上下文用全角标点、数字用半角                              | 正则                           |
| UX-20 | 专有名词大小写（GitHub 而非 Github）、不用劣质缩写（h5/FED）  | 词典精确匹配                   |

实现可用 `autocorrect-py`（Rust 核心 Python 绑定，指北工具表推荐）作为校验器实现或对照基准。争议项（直角引号「」等）作为模板风格决策，不进校验器。

## 4. 信息架构与响应式

| ID    | 项       | 规定                                                                        |
| ----- | -------- | --------------------------------------------------------------------------- |
| UX-21 | 导航四区 | 阅读中心（默认）/ 仓库库 / 分析管理 / 系统设置（顶栏横向导航，UX-61）        |
| UX-22 | 桌面     | ≥1366px 顶栏 + 居中正文（--sd-width）+ 右目录 200px（钉右侧视口边缘）        |
| UX-23 | 平板     | <1366px 目录收起                                                            |
| UX-24 | 移动     | <768px 顶栏收紧（快捷键提示隐藏）                                           |
| UX-25 | 断点手测 | 390/768/1024/1440（390/1440 为 PRD NFR-05 验收口径）                           |

## 5. 阅读进度（跨设备恢复）

采用 omnivore 的**锚点 + 视口百分比 + 高水位**模型（`reference/omnivore/packages/db/migrations/0120.do.library_item.sql`、`packages/api/src/services/library_item.ts:1002-1021`）：

| ID    | 项         | 规定                                                                                                                 |
| ----- | ---------- | -------------------------------------------------------------------------------------------------------------------- |
| UX-26 | 进度存储   | 每个报告版本存：`anchor`（当前章节/段落索引）、`top_percent`/`bottom_percent`（视口两端百分比）、`highest_read_anchor`（高水位） |
| UX-27 | 写入防回退 | 仅当新位置 > 已存位置才更新（高水位 CASE-update 语义）；「显式重置到开头」用 0 值特判；**进入文章默认开头**，恢复经「继续上次」显式触发 |
| UX-28 | 上报节流   | 客户端写本地，空闲批量合并上报（omnivore 用 Redis 缓存 + 60s 扫描合并，我们对应 localStorage + 定时回传，单用户无需队列） |
| UX-29 | 版本更新   | 跨版本自动迁移为可延后项（PRD REQ-RPT-004、SCP-03）；若启用，优先按同名章节恢复，锚点匹配失败回开头，旧进度不套用                       |

## 6. 格式调节与持久化

沿用 omnivore 的调节项与持久化方式（`packages/web/lib/hooks/useReaderSettings.tsx`），映射到三档宽度：

| ID    | 项       | 范围/步进                                               | 持久化                 |
| ----- | -------- | ------------------------------------------------------- | ---------------------- |
| UX-30 | 字号     | 12–22px，±1，键盘 `[` `]`                               | localStorage           |
| UX-31 | 正文宽   | 62ch / 72ch / 88ch 三档                                 | localStorage + 账户配置 |
| UX-32 | 行高     | 1.6 / 1.8 / 2.0                                         | localStorage           |
| UX-33 | 主题     | 浅 / 深 / 跟随系统（auto 同 wallabag `dark-theme#useAuto`） | localStorage + 账户配置 |
| UX-34 | 强对比文本 | bool                                                  | localStorage           |

## 7. 键盘与搜索交互

照抄 miniflux 的处理器结构与注册表（`internal/ui/static/js/keyboard_handler.js`、`app.js:1180-1218`）：

| ID    | 项     | 规定                                                                                 |
| ----- | ------ | ------------------------------------------------------------------------------------ |
| UX-35 | 处理器 | 两键队列支持 `g u` 前缀组合；输入框聚焦时全部忽略；修饰键过滤                         |
| UX-36 | 导航键 | `g u/b/h/s` → 阅读中心/仓库库/分析管理/设置；`/` 搜索；`g g`/`G` 顶/底                |
| UX-37 | 阅读键 | `j/k` 上下条目、`o/Enter` 打开、`m` 已读切换、`f` 收藏、`?` 帮助                      |

**搜索弹层交互规格**（依据 VitePress 本地搜索 `VPLocalSearchBox.vue`）：

| ID    | 项         | 规定                                                                                                                                                    |
| ----- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-38 | 结果与节流 | 结果上限 16–20 条、输入 debounce 200ms；查询持久化 sessionStorage、视图偏好 localStorage                                                                |
| UX-39 | 输入法回车 | **键盘回车必须先判 `e.isComposing`**——中文输入法确认候选词的回车不得触发跳转（VitePress `L353-357`，中文产品硬要求）                                     |
| UX-40 | 键盘环绕   | 环绕式 ↑↓ 选择 + `scrollIntoView({block:'nearest'})`；键盘移动时禁用鼠标 hover 高亮；focus-trap 包住弹层                                                |
| UX-41 | 命中片段   | 直接渲染 FTS5 `snippet()` 产出（服务端先转义正文再包 `<mark>`，`<mark>` 进 nh3 白名单）；结果按「报告 > 章节」两级分组——索引时同 VitePress `title/titles` 模型存父级章节链（ADR-0008 token `map` 提供） |
| UX-42 | 空结果态   | 延迟出现，避免输入过程中的闪烁                                                                                                                          |

## 8. 证据标注视觉语言（差异化组件）

五类证据 = 图标 + 文字标签 + 结构差异（行内标记 + 引用块两种形态），**虚线只属于「分析推断」**：

| ID    | 类型       | 视觉                                                                       | 形态   |
| ----- | ---------- | -------------------------------------------------------------------------- | ------ |
| UX-43 | 源码事实   | 实线左缘 + 代码图标 + 等宽 `路径:行号`，可点击开固定 commit 源文件          | 引用块 |
| UX-44 | 作者说明   | 实线左缘 + 链接图标 + 外链标注时间                                         | 引用块 |
| UX-45 | 分析推断   | **虚线左缘** + 中性色，正文首词「分析推断：」                              | 引用块 |
| UX-46 | 外部背景   | 外链图标 + 来源与查阅时间                                                  | 标签块 |
| UX-47 | 未知/冲突  | 问号图标 + 「证据不足」，明确不消除矛盾                                    | 提示条 |

| ID    | 项         | 规定                                                                                                          |
| ----- | ---------- | ------------------------------------------------------------------------------------------------------------- |
| UX-48 | 图表与表格 | mermaid 渲染区 + 图题 + 放大层（滚轮缩放、Esc 退出、焦点圈闭）+ 文字后备折叠；宽表格容器内滚动，页面不横向溢出 |

## 9. 无障碍

| ID    | 项         | 规定                                                                           |
| ----- | ---------- | ------------------------------------------------------------------------------ |
| UX-49 | 焦点环     | 2px `--sd-focus`（对应 miniflux 焦点 box-shadow 用法）                          |
| UX-50 | 交互目标   | ≥44px                                                                          |
| UX-51 | 状态编码   | 三重编码（图标+文字+色）                                                        |
| UX-52 | 语义结构   | 语义地标与跳转链接；`color-scheme` 声明使原生控件跟随主题                       |
| UX-53 | 动效降级   | `prefers-reduced-motion` 降级动效                                               |

## 10. 产品图标

| ID    | 项     | 规定                                                                                                                                                              |
| ----- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-54 | 图标   | 五角星三层切片、顶片琥珀（提取出的设计）、逐级右移——「星剖」直译；单色变体（[icons/mono/icon-a-mono.svg](icons/mono/icon-a-mono.svg)，`fill:currentColor` 随上下文着色）用于 favicon、暗色顶栏与单色场景；落地：favicon.svg（全细节）+ favicon-bold.svg（小尺寸简化变体）+ 16/32/48px favicon + favicon.ico + apple-touch 180 + PWA 192/512 + site.webmanifest（web/public/，`npm run icons` 再生成）；页面已接线 index.html；预览基准见 [icons/preview.html](icons/preview.html) 的 A 行 |

## 11. 实施映射（Vue 3）

| ID    | 项           | 落地                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ----- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UX-55 | tokens       | `web/src/styles/tokens.css`：明暗轴 × 字体轴成对变量块，组件零硬编码色值（miniflux 6 bundle 的等价物：运行时切换变量而非编译期拼 bundle）                                                                                                                                                                                                                                                                                                                                                                                                                          |
| UX-56 | 组件树       | 顶栏 AppShell（Naive UI provider + 主题映射）→ `ReadingHome` / `ReportView`（`useScrollSpy`、`useReadingProgress`、`EvidenceBlock`、`FigureFrame`）→ `RepoLibrary`（N 抽屉）/ `AnalysisBoard` / `SettingsView`；composables 见 UX-58 |
| UX-57 | 渲染分工     | Markdown 服务端渲染（ADR-0008），token 流的 `map` 行号用于目录树与命中片段回源（见 ADR-0007/0008 依据）                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| UX-58 | composables  | 键盘处理器、进度回传、格式调节为独立 composable：`useKeyboard` / `useReadingProgress` / `useReaderSettings`                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| UX-59 | 目录 scrollspy | 直接改写 VitePress `useActiveAnchor`（`reference/vitepress/src/client/theme-default/composables/outline.ts:79-205`）：scroll 监听 + `throttleAndDebounce(100)`（首调立即、尾部防抖）；判定 = 「最后一个越过视口顶（+`scroll-margin-top`+4px 容差）的标题」，页顶置空、页底取最后一个标题；坐标用 `offsetParent` 链累加（`getAbsoluteTop`，过滤 `display:none`）；点击目录置 `ignoreScrollOnce` 防高亮闪跳；左侧滑动指示条按 `offsetTop` 定位并 `scrollIntoView(block:'nearest')`。若 ReportView 用独立滚动容器，监听该容器并换算容器内偏移（VitePress 监听 window、Docusaurus 监听 document，二者差异在此） |
| UX-60 | 组件库 Naive UI | 主题经 n-config-provider themeOverrides 完全映射本规范 tokens（web/src/theme.js），深浅两轴成对；组件零硬编码色值原则不变                                                          |
| UX-61 | 布局范式：顶栏 + 居中内容 | VitePress/Linear 式吸顶顶栏；内容列居中占主体；文章页大纲右浮（≥1366px，auto-trend 风格：本页大纲标题/hairline/主色指示）；页面容器统一 .page（8 基数纵向间距） |
| UX-62 | 标签双轨展示 | 仓库抽屉「标签」区:自动标签 info 芯片（AI 分类生成,auto_tags）与人工标签分区显示;自动标签入检索域 |

## 12. 依据索引

| 选择                                             | 依据                                                                          |
| ------------------------------------------------ | ----------------------------------------------------------------------------- |
| 灰阶+单强调+状态聚焦、focus/current-item 用法     | `reference/miniflux/internal/ui/static/css/dark.css:42-43,84-86`              |
| 明暗×字体双轴、color-scheme、reduced-motion       | `miniflux .../static.go:79-85`、`dark.css:117-119`、`common.css:91-95`        |
| 排版数字与引用/代码/图处理                        | `miniflux .../css/common.css:1100-1216`                                       |
| 长列表渲染性能                                    | `miniflux .../common.css:831-835`                                             |
| 键盘前缀模型与注册表                              | `miniflux .../keyboard_handler.js:8-45`、`app.js:1180-1218`                   |
| 进度模型（锚点+百分比+高水位+批量合并）           | `omnivore .../0120.do.library_item.sql:35-38`、`library_item.ts:1002-1021`、`sync_read_positions.ts:12-47` |
| 格式调节项与持久化                                | `omnivore .../useReaderSettings.tsx:10-33,117-133`                            |
| 主题 auto（跟随系统）                             | `wallabag/templates/Entry/entry.html.twig:150-158`                            |
| 高亮/批注实体形态（预留扩展）                     | `omnivore .../0022.do.highlights.sql:5-19`                                    |
| 目录 scrollspy 算法（节流/判定/容差/防闪跳）      | `reference/vitepress/src/client/theme-default/composables/outline.ts:79-221`  |
| 搜索弹层交互（16 条/200ms/isComposing/键盘环绕/分组） | `reference/vitepress/src/client/theme-default/components/VPLocalSearchBox.vue:86-373` |
| 中文排版硬性规范与白名单机制                      | `reference/chinese-copywriting-guidelines/README.zh-Hans.md:19-250`           |
