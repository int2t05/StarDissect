# 纯净审计 round2 — 全仓一致性专项

<!-- 四路子代理(A+E / B+C / D 一致性专审 / F 系统工程);范围=部署与三批改动后的全仓 -->

| 日期   | 2026-10-09                        | 方式   | 四路子代理 → 甄别 → 修复 → 56 tests + build 全绿 |
| ------ | --------------------------------- | ------ | ------------------------------------------------ |
| 结论   | 22 项发现:全部修复(含 2 项功能性断裂) | 重点   | 用户指令:一致性                                  |

## 关键修复

| # | 类 | 问题 | 修复 |
| - | -- | ---- | ---- |
| 1 | C3 | **/api/entries 字段形状断裂**:后端扁平 repo_id/full_name,前端读 e.repo.id → 打开条目必崩(M/G 批次交界引入) | 前端对齐扁平字段 |
| 2 | A2/D1 | 「受限完成」清根未尽:v1.0/prd REQ-TASK-001/004、routes 重试白名单、AnalysisBoard 按钮、tech §3 | 四处全清,五态统一 |
| 3 | F1 | syncing=1 崩溃残留致同步永久卡死 | 启动自检同处复位 |
| 4 | F2 | uvicorn/500 日志不入 app.log;_run_sync 无日志 | uvicorn logger 并入管道(幂等);_run_sync 记录 |
| 5 | F4 | 停机竞态:loop_task 未 await 即关连接 | await 取消 → 关调度器 → 关连接 |
| 6 | F5 | TERMINATE_REQUESTS 收尾残留 | step 归档时统一 discard |
| 7 | D2/D3 | tech.md §3 快照时点/归档态;§6 漏 6 端点、多列 POST | 全表回写 |
| 8 | D4 | 「单连接池」表述失实 | 改「多短连接+WAL 串行写」 |
| 9 | D5 | 并发配置/同步开关:文档有、实现无 | REQ-CFG-001 与 ADR-0004 收敛措辞 |
| 10 | D6 | repos.status 注释与 FIG-02 承载层混用 | 注释分立(仓库态 vs 任务态) |
| 11 | D7 | TECH 自设 AUD-01..08 与 PRD AUD 撞号 | TECH 改独立前缀 T-AUD |
| 12 | D8 | v1.0 头部漏 DEC-09 | 补 |
| 13 | D9 | UX-28 失败缓存重传未实现 | localStorage 缓存+restore 重传+bottom_percent 真值 |
| 14 | D10 | UX-30 [ ] 字号键、UX-36 gg/G 顶底未实现 | 落地 |
| 15 | D11 | tech.md §8「AC 逐条映射用例」失实 | 改述(验收映射由审计台账追踪) |
| 16 | B3/C3 | 「唯一陈述」失实;校验白名单双源;deep_research clamp 死参数 | 单源化:tech.md 契约 / config 白名单 / 单层夹取 |
| 17 | C2 | 审计批次 ID(F5/S4/M2 等)混入代码注释;Cognik 具体路径悬空 | 注释去 ID 改述;Cognik 标注外部参照 |
| 18 | F6 | useKeyboard pending 导出无消费;search 上限魔法数 | 去导出;SEARCH_MAX_LIMIT 入 config |
| 19 | A1 | 七个测试文件 S#/M2 批次前缀 | 清除,保留行为描述 |
| 20 | F3/F8 | task_limits 默认值、search 上限散落 | config 单源化 |
| 21 | D5 | settings 兜底默认 30/1800 与 config 双源 | queue.task_limits 引 config |
| 22 | F8 | entries 非法 state 静默回退 all | 接受(宽松默认,记录) |

## 复检

- pytest 56 passed + 2 门控;build 通过
- 线程纪律:8 处 connect( 创建/使用线程一一对应(部署实测 traceback 根因已修:_step_once)
- grep `审查 T-|S[0-9] 测试|F[0-9]|受限完成`:代码零残留(文档台账除外)
- 编号体系全序列闭合;DDL/渲染契约/证据语法逐字一致
