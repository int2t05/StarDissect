# ADR-0003 GitHub 同步:gidgethub 增量同步

状态:草案 · 2026-10-09

## 背景

REQ-SYNC-001:定时+手动同步 star 列表,增量比对,排除 fork/archive;限流时本轮跳过。

## 决策

用 gidgethub(异步 GitHub API 库)拉取 star 列表与仓库元数据;以 star 时间游标做增量;fork/archive 在入库前过滤。

## 理由与落选

- PyGithub:同步阻塞模型,与 FastAPI 事件循环不亲和,需线程包裹。落选。
- shell 调 gh CLI:进程边界+解析脆弱。落选。
- gidgethub 本身异步原生、零重依赖,与 ADR-0001 同一事件循环;官方定位「An asynchronous GitHub API library」(reference/gidgethub/README.rst,查阅 2026-10-09)。

## 影响

同步器为纯 async 函数,由 ADR-0004 的调度器触发;凭据为 personal access token(settings 表,REQ-CFG-001);增量游标存 sync_runs,失败不推进游标(下轮自然重试)。

## 参考

- reference/gidgethub/README.rst(查阅 2026-10-09):异步 GitHub API 库定位与 sans-io 设计。
- GitHub REST API docs https://docs.github.com/rest(查阅 2026-10-09):starring 列表分页与排序语义(按 starred_at)。
