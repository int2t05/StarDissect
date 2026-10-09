# ADR-0004 调度 APScheduler + 进程内 asyncio 任务队列

状态:草案 · 2026-10-09

## 背景

REQ-TASK-001…006:自动队列(新 star 优先)、干预(暂停/优先级/取消/排除)、轮次+时限限额、重试、中断恢复;REQ-SYNC-001 每日定时。单进程运行(ADR-0001)。

## 决策

- 定时触发:APScheduler 3.x(stable;4.0 为 pre-release,官方警告不可用于生产,见参考)。
- 分析队列:进程内 asyncio 工作循环,消费 SQLite tasks 表(状态机=docs/PRD.md FIG-02);并发数可配置(默认 1,OPN-02)。队列表即持久层:重启后排队任务原样保留,「分析中」标记中断(REQ-TASK-006)。

## 理由与落选

- huey/redis 等外部队列:引入第二存储/进程,单用户无消费者竞争。落选。
- 纯 asyncio 定时 loop(手写 cron):重造调度轮子,边界语义(错过触发、并发池)易错。落选。
- 先例:APScheduler 官方 v4 预发布警告要求选 3.x(reference/apscheduler/README.rst,查阅 2026-10-09);healthchecks 以「简单定时+持久状态」模型管理任务(reference/healthchecks,形态参照)。

## 影响

队列干预=对 tasks 表的状态/优先级字段更新,工作循环每轮读取,天然持久;「终止分析中任务」由 agent 运行层的取消机制承接(ADR-0005)。

## 参考

- reference/apscheduler/README.rst(查阅 2026-10-09):v4.0 pre-release 警告→选 3.x。
- reference/healthchecks/(查阅 2026-10-09):定时+持久任务状态的极简模型参照。
