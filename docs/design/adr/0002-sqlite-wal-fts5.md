# ADR-0002 SQLite 单库:WAL + FTS5

状态:草案 · 2026-10-09

## 背景

数据形态:仓库/任务/报告版本/知识点/进度等结构化记录 + 章节级全文索引;单写者(应用自身);单机部署(ADR-0001)。

## 决策

单一 SQLite 数据库文件,启用 WAL;全文索引用 SQLite 内置 FTS5(external content 模式,索引对象为章节表,见 ADR-0006)。

## 理由与落选

- PostgreSQL/MySQL:独立服务进程+运维,单用户规模收益为零。落选。
- 多库拆分(业务/索引分库):无瓶颈动机,徒增事务边界。落选。
- 先例:pocketbase 以 SQLite 为嵌入式默认库承载自托管应用全量数据(reference/pocketbase/README.md);sqlite-vec 的存在佐证 SQLite 生态对检索类负载的扩展能力(本项目 v1.0 不用向量,仅记录可扩展方向)。

## 影响

备份=复制单文件(+WAL checkpoint);读写并发依赖 WAL;FTS5 与业务表同库,索引与正文事务一致(REQ-SRCH-001 索引补建语义简化)。

## 参考

- reference/pocketbase/README.md(查阅 2026-10-09):SQLite 承载自托管应用全量数据先例。
- SQLite FTS5 官方文档 https://www.sqlite.org/fts5.html(查阅 2026-10-09):external content 与 snippet() 能力,支撑命中片段(REQ-SRCH-001)。
