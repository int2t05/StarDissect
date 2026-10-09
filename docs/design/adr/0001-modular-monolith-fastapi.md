# ADR-0001 模块化单体:Python + FastAPI

状态:草案 · 2026-10-09

## 背景

单用户内网自托管(DEC-04),200 仓库规模(DEC-08),PRD 全量闭环 v1.0。部署者即使用者,无团队协作与横向扩展需求。

## 决策

单进程 FastAPI 应用承载全部六模块(FIG-01),Vue 3 SPA 构建产物由同进程静态托管。Python 3.12+。

## 理由与落选

- 微服务/多进程拆分:无 scaling 动机,徒增部署与事务一致性成本。落选。
- Go/Node 后端:Python 生态与本项目核心依赖(pydantic-ai、jieba、markdown-it-py)同源,类型化 Agent 框架仅 Python 成熟。Go 单二进制分发优势(miniflux 形态)以牺牲 Agent 生态为代价,不划算。落选。
- 先例:pocketbase 以单二进制单体服务单用户自托管场景(reference/pocketbase/README.md:「embedded database (SQLite)」);fastapi-best-practices 提供模块化分层结构范式(reference/fastapi-best-practices,src/ 分层:router→service→crud)。

## 影响

部署=一个进程+一个 SQLite 文件;模块间调用为进程内函数调用;未来拆分的缝留在「任务队列」与「agent」边界(ADR-0004/0005)。

## 参考

- reference/pocketbase/README.md(查阅 2026-10-09):单用户自托管单体形态;采纳形态,不采用其 Go/嵌入库路线。
- reference/fastapi-best-practices/(查阅 2026-10-09):采纳分层与项目结构范式;其多环境/多租户内容不适用。
