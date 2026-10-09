# 纯净审计 round2 修复脚本批次 2(逐条 assert):完成后删除
import io

def apply(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, f'MISS {path}: {old[:60]!r}'
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print('ok', path)

# ---- main.py:uvicorn 日志接入、幂等、syncing 复位、停机顺序 ----
apply('server/app/main.py', [
    ('''def setup_logging() -> None:
    # 可观测性基座:stdout + 轮转文件,双路输出
    config.logs_dir().mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handlers = [logging.StreamHandler(), logging.handlers.RotatingFileHandler(
        config.logs_dir() / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)''',
     '''def setup_logging() -> None:
    # 可观测性基座:stdout + 轮转文件双路输出;uvicorn 日志并入同管道;幂等(测试多次装配)
    config.logs_dir().mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handlers = [logging.StreamHandler(), logging.handlers.RotatingFileHandler(
        config.logs_dir() / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")]
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    logging.getLogger("apscheduler").setLevel(logging.WARNING)'''),
    ('''        recovered = queue.recover(conn)
        if recovered:
            logger.info("启动恢复:%d 个中断任务等待人工重试", recovered)''',
     '''        recovered = queue.recover(conn)
        if recovered:
            logger.info("启动恢复:%d 个中断任务等待人工重试", recovered)
        conn.execute("INSERT INTO settings(key, value) VALUES ('syncing','0')"
                     " ON CONFLICT(key) DO UPDATE SET value='0'")  # 崩溃残留复位,手动/定时同步不再卡死
        conn.commit()'''),
    ('''        yield
        if loop_task:
            loop_task.cancel()
            logger.warning("停机:进行中任务将标记中断,重启后由 recover 兜底等待人工重试")
        if scheduler:
            scheduler.shutdown(wait=False)
        conn.close()''',
     '''        yield
        if loop_task:
            loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await loop_task  # 等待循环退出,消除与调度器的关闭竞态
            logger.warning("停机:进行中任务将标记中断,重启后由 recover 兜底等待人工重试")
        if scheduler:
            scheduler.shutdown(wait=False)
        conn.close()'''),
])

# ---- config:新常量 ----
apply('server/app/config.py', [
    ('''CLASSIFIER_TIMEOUT_SEC = 120''',
     '''CLASSIFIER_TIMEOUT_SEC = 120
CLASSIFIER_REQUEST_LIMIT = 3
TASK_DEFAULT_TURN_LIMIT = 30
TASK_DEFAULT_TIME_LIMIT_SEC = 1800
SEARCH_MAX_LIMIT = 50'''),
])

# ---- queue.task_limits 默认值单源 config;step 清尾终止请求 ----
apply('server/app/tasks/queue.py', [
    ('''def task_limits(conn: sqlite3.Connection) -> dict:
    """从设置读取任务限额默认值(公共入口,同步器与 API 共用)。"""
    s = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {"turn_limit": int(s.get("turn_limit", "30")), "time_limit_sec": int(s.get("time_limit_sec", "1800"))}''',
     '''def task_limits(conn: sqlite3.Connection) -> dict:
    """从设置读取任务限额默认值(公共入口,同步器与 API 共用)。"""
    from app import config

    s = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {"turn_limit": int(s.get("turn_limit", str(config.TASK_DEFAULT_TURN_LIMIT))),
            "time_limit_sec": int(s.get("time_limit_sec", str(config.TASK_DEFAULT_TIME_LIMIT_SEC)))}'''),
    ('''    logger.info("任务归档 id=%s repo=%s status=%s reason=%s", task["id"], task["repo_id"], status, reason)''',
     '''    TERMINATE_REQUESTS.discard(task["id"])  # 清尾:任务已终态,未消费的终止请求不留残
    logger.info("任务归档 id=%s repo=%s status=%s reason=%s", task["id"], task["repo_id"], status, reason)'''),
])

# ---- routes:_run_sync 日志;search 上限单源 ----
apply('server/app/api/routes.py', [
    ('''async def _run_sync(token: str):
    from app.main import db_path  # 与应用同一数据目录

    conn = connect(db_path())
    try:
        await syncer.sync_star(conn, token)
    finally:''',
     '''async def _run_sync(token: str):
    from app.main import db_path  # 与应用同一数据目录

    conn = connect(db_path())
    logger = logging.getLogger("stardissect.sync")
    try:
        counts = await syncer.sync_star(conn, token)
        logger.info("手动同步完成:%s", counts)
    except Exception:
        logger.exception("手动同步失败")
        raise
    finally:'''),
    ('''    return indexer.search(request.app.state.conn, q, limit=min(limit, 50))''',
     '''    return indexer.search(conn, q, limit=min(limit, config.SEARCH_MAX_LIMIT))'''),
    ('''    if not q.strip():
        return []
    return indexer.search''',
     '''    if not q.strip():
        return []
    return indexer.search'''),
])
# search 引用还有一处 request.app.state.conn 残留则统一替换
s = io.open('server/app/api/routes.py', encoding='utf-8').read()
s = s.replace('request.app.state.conn', 'conn')
if 'import logging' not in s:
    s = s.replace('from fastapi import APIRouter', 'import logging\n\nfrom fastapi import APIRouter', 1)
io.open('server/app/api/routes.py', 'w', encoding='utf-8', newline='\n').write(s)

# ---- runner:classifier 轮次单源 ----
apply('server/app/agents/runner.py', [
    ('usage_limits=UsageLimits(request_limit=3))', 'usage_limits=UsageLimits(request_limit=config.CLASSIFIER_REQUEST_LIMIT))'),
])

# ---- validator:白名单单源 config ----
apply('server/app/render/validator.py', [
    ('''import re

from app import config''', '''import re

from app import config'''),
    ('''WHITELIST = {"GitHub", "GitLab", "TypeScript"}


def validate''', '''def validate'''),
    ('        has_product = any(w in line for w in config.TYPOGRAPHY_WHITELIST)' if 'config.TYPOGRAPHY_WHITELIST' not in io.open('server/app/render/validator.py', encoding='utf-8').read() else '        has_product = any(w in line for w in WHITELIST)',
     '        has_product = any(w in line for w in config.TYPOGRAPHY_WHITELIST)'),
])

# ---- websearch:clamp 修正、措辞、Cognik 路径 ----
apply('server/app/agents/websearch.py', [
    ('# 网络搜索工具链(参考 Cognik:server/internal/infra/adapter/search_client.go 降级链模式)',
     '# 网络搜索工具链(降级链模式参照外部项目 Cognik 的 SearchChain 设计)'),
    ('    results = await chain.search(query, max(config.MAX_DEEP_PAGES, max_pages))',
     '    results = await chain.search(query, min(max_pages, config.MAX_DEEP_PAGES))'),
])
apply('server/app/agents/tools.py', [
    ('# 证据锚定:read_file/search_code 输出带真实行号,供 [source] 证据引用(REQ-RPT-002)\n# 网络搜索纪律(线索≠证据)的唯一陈述在 tech.md §4,此处工具 docstring 仅简述并回指',
     '# 证据锚定:read_file/search_code 输出带真实行号,供 [source] 证据引用(REQ-RPT-002)\n# 「线索≠证据」纪律的契约见 docs/v1.0/tech.md §4,此处仅简述'),
])
apply('docs/v1.0/tech.md', [
    ('| web_search      | 网络搜索,降级链 Tavily→Exa→DuckDuckGo(参考 Cognik SearchChain);片段是线索非证据 | 外部背景(引用前须 web_fetch 核实) |',
     '| web_search      | 网络搜索,降级链 Tavily→Exa→DuckDuckGo;片段是线索非证据 | 外部背景(引用前须 web_fetch 核实) |'),
])
print('batch2 core done')
