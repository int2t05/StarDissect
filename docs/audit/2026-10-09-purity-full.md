# 纯净全量审计报告 — 全仓(docs + server + web + test)

<!-- 六路子代理并行审计:A 溯源残留 / B 装饰冗余 / C 死内容 / D doc-impl 裂隙 / E 语言平台残留 / F 系统工程(稳定性·日志·报错·可维护性) -->

| 日期   | 2026-10-09                        | 范围   | docs/**、server/app/**、web/src/**、test/**(豁免 reference/、依赖、产物、审计台账自身) |
| ------ | --------------------------------- | ------ | ------------------------------------------------------------ |
| 结论   | 六类共 45 项发现:修复 38,接受 6,待人工 1 | 方式   | 分子代理隔离审计 → 主上下文甄别修复 → 52 tests + build 全绿 |

## 发现与处置(A–E + F)

| 类 | 发现数 | 代表项 | 处置 |
| -- | ------ | ------ | ---- |
| A 溯源残留 | 13 | 代码注释 10 处「审查 T-xx」修复标记;ADR-0006「修订框架」、ADR-0007/0008「自此闭合」、tech.md「(ADR-0006 修订)」 | 全部清除:注释只述当前行为;ADR-0006 重写为当前决策(external content 矛盾移入落选理由) |
| B 装饰冗余 | 12 | FIG-03 判装饰(用户「多 mermaid」指令在先,豁免保留);tech.md §6 API 表漂移;「线索≠证据」四处各述;syncer 私有入队复用 enqueue;掩码哨兵改「空=保留」;helpVisible 占位落地为帮助浮层 | 修复/豁免 |
| C 死内容 | 12 | repos.head_commit、sync_runs.cursor 死列;github_user/concurrency 死配置;GET /api/sync 无前端消费;UIUX-34 强对比无实现;pygments 零调用;models.py/server-tests 幽灵声明 | 死列死配置删除;设置页补最近同步展示;强对比轴落地;pygments 移除(依赖+文档);幽灵声明清除 |
| D doc/impl 裂隙 | 12 | 「受限完成」生产不可达;「待处理」无产生动作;软删除无恢复;token 无校验;浅克隆声明「检出 head_commit」失实;API 表六端点未列 | 待处理闭环(混合/未识别→待处理,任务归档);恢复端点补齐;token 实时校验(失败不影响他项);tech.md §1/§2/§4/§6 回写;受限完成→见待人工 |
| E 语言平台 | 2 | 「feed」英文混词;mermaid 走外部 CDN(违背内网自托管) | 措辞改「订阅源」;mermaid 改本地依赖随构建打包 |
| F 系统工程 | 11 | **全项目零日志**;队列循环静默重试;定时同步 suppress(Exception);clone stderr 丢失;classifier 触限裸英文;前端 fetch 无 catch 白屏;魔法数散落;API 单连接事务交错 | **logging 体系落地**(stdout+轮转文件,8 类关键事件);错误全透出;fetch 统一 api() 帮手+toast;clone 携带 git stderr;classifier 触限中文化;魔法数入 config;API 连接交错见接受项 |

## 待人工确认(1 项)

「受限完成」语义:REQ-TASK-003 要求「超限有产出→受限完成保留产出」,但 v1.0 实现 = 超限即失败(部分产出需增量落库,复杂度与快速原型不符)。建议改 REQ 语义为「超限即失败,可重试」,或排期实现增量落库。状态位与归档路径已保留,不阻塞。

## 接受项(记录理由)

- API 侧单连接(app.state.conn)在手动同步期间与后台任务交错 commit:单用户低并发 + WAL 串行写,风险有限,列下批改进(per-request 连接)。
- web_fetch 无 SSRF 限制:单用户内网部署(DEC-04),agent 工具作用域已限克隆区,外网抓取本身即功能。
- ReadingHome 逐仓库串行拉版本:200 规模可接受。
- FIG-03 判定为装饰性:与「项目级 PRD 多 mermaid」的用户指令冲突,指令优先保留。

## 复检

- grep `审查 T-|修订 |自此闭合`:零残留(审计台账自身除外)
- `uv run pytest`:52 passed, 2 skipped(真实网络门控)
- `npm run build`:通过(mermaid 本地打包)
- 编号体系 UX-01..59 / REQ 九域 / AC-001..028 / ADR-0001..0008 连续无跳号
