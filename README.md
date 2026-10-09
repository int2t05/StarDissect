# 星剖 StarDissect

自托管的 GitHub Star 深度解析工具:自动同步并分类 star 收藏,由实现 agent 深读源码,生成证据可溯源的中文精读报告。

- 需求: [docs/PRD.md](docs/PRD.md)(项目级)· [docs/v1.0/prd.md](docs/v1.0/prd.md)(v1.0 详规)
- 架构: [docs/TECH.md](docs/TECH.md) · [docs/design/adr/](docs/design/adr/) · [docs/v1.0/tech.md](docs/v1.0/tech.md)
- 界面: [docs/uiux/UIUX.md](docs/uiux/UIUX.md) · 审计: [docs/audit/](docs/audit/)

## 快速开始

依赖:Python 3.13+ 与 [uv](https://docs.astral.sh/uv/)、Node 20+、git。

```bash
# 1. 配置密钥(不入库;.env 不会被 git 追踪)
cp .env.example .env   # 填入 GITHUB_TOKEN / AI_* / 搜索 key

# 2. 前端构建
cd web && npm install && npm run build && cd ..

# 3. 启动(仓库根运行;数据落 data/)
uv run --project server python -m uvicorn app.main:app --app-dir server --port 8000

# 4. 打开 http://127.0.0.1:8000 →「系统设置」核对配置 →「立即同步」
```

同步完成后仓库自动入队分析(agent 受轮次/时限约束,详见 DEC-03/09);新报告出现在「阅读中心」与 `/rss.xml`。

## 测试

```bash
uv run --project server pytest          # 52 项;真实网络用例由环境变量门控
cd web && npm run build                  # 前端构建校验
```

门控用例(需真实凭据,默认跳过):`STARDISSECT_IT_LLM=1`(配 AI key)、`STARDISSECT_IT_GH=1`(配 GITHUB_TOKEN)。

## 运行要点

- 数据:SQLite 单文件(`data/app.db`,WAL);日志:`data/logs/app.log`(轮转)
- 安全:应用无登录,仅限内网;暴露公网必须经反向代理鉴权(DEC-04/OPN-08),密钥只存服务端、界面仅回显尾号
- 队列:默认自动推进,可在「分析管理」暂停/调优先级/取消/重试;服务重启后进行中任务标记「中断」待人工重试(REQ-TASK-006)
