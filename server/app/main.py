# 应用装配:单进程 FastAPI(ADR-0001);调度+队列随 lifespan 启动(ADR-0004)
import asyncio
import contextlib
import logging
import logging.handlers
import os
from pathlib import Path
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.agents import runner
from app.api import routes
from app.db import connect, init_db
from app.tasks import queue

logger = logging.getLogger("stardissect")


def setup_logging() -> None:
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
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def _queue_loop():
    # 服务循环:独立连接(与 API 连接写者隔离);异常记日志后重试,不静默假活
    conn = connect(config.db_path())
    while True:
        try:
            stepped = await asyncio.to_thread(queue.step, conn, _execute)
            await asyncio.sleep(config.QUEUE_INTERVAL_ACTIVE if stepped else config.QUEUE_INTERVAL_IDLE)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("队列循环异常,%.0fs 后重试", config.QUEUE_RETRY_ON_ERROR)
            await asyncio.sleep(config.QUEUE_RETRY_ON_ERROR)


def _execute(task_id: int):
    # 同步桥:工作线程独立连接;watcher 轮询终止请求(REQ-TASK-002)
    conn = connect(config.db_path())
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    repo = conn.execute("SELECT * FROM repos WHERE id=?", (task["repo_id"],)).fetchone()
    logger.info("任务开始 id=%s repo=%s turn_limit=%s time_limit=%ss", task_id, repo["full_name"], task["turn_limit"], task["time_limit_sec"])

    async def _run():
        run = asyncio.ensure_future(runner.run_task(conn, task, repo))
        term = asyncio.ensure_future(_watch_terminate(run, task_id))
        try:
            return await run
        finally:
            term.cancel()

    try:
        return asyncio.run(_run())
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("任务执行异常 id=%s repo=%s", task_id, repo["full_name"])
        raise


async def _watch_terminate(run, task_id: int):
    while True:
        if task_id in queue.TERMINATE_REQUESTS:
            queue.TERMINATE_REQUESTS.discard(task_id)
            logger.info("任务被人工终止 id=%s", task_id)
            run.cancel()
            return
        await asyncio.sleep(config.TERMINATE_POLL_SEC)


def create_app(data_dir: str | None = None, workers: bool = True) -> FastAPI:
    if data_dir:
        os.environ["STARDISSECT_DATA"] = data_dir
    config.load_env()
    setup_logging()
    init_db(config.db_path())
    _seed_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(config.db_path())  # 生命周期内自建自管(事件循环线程)
        recovered = queue.recover(conn)
        if recovered:
            logger.info("启动恢复:%d 个中断任务等待人工重试", recovered)
        # 启动自检:关键配置缺失时给出可行动提示
        keys = {r["key"] for r in conn.execute("SELECT key FROM settings")}
        for key, hint in (("github_token", "star 同步不可用"), ("ai_model", "分析任务不可用")):
            if key not in keys:
                logger.warning("启动自检:未配置 %s,%s", key, hint)
        scheduler = None
        loop_task = None
        if workers:
            loop_task = asyncio.create_task(_queue_loop())
            scheduler = AsyncIOScheduler()
            async def _daily_sync():
                # 定时同步(REQ-SYNC-001);进行中跳过本轮(REQ-SYNC-002 合并语义);失败不再静默
                row = conn.execute("SELECT value FROM settings WHERE key='github_token'").fetchone()
                flag = conn.execute("SELECT value FROM settings WHERE key='syncing'").fetchone()
                if not row:
                    logger.info("定时同步跳过:未配置 github_token")
                    return
                if flag and flag["value"] == "1":
                    logger.info("定时同步跳过:手动同步进行中")
                    return
                from app.sync import syncer

                try:
                    counts = await syncer.sync_star(conn, row["value"])
                    logger.info("定时同步完成:%s", counts)
                except Exception:
                    logger.exception("定时同步失败(下轮重试)")

            scheduler.add_job(_daily_sync, "cron", **config.DAILY_SYNC_CRON)
            scheduler.start()
        yield
        if loop_task:
            loop_task.cancel()
            logger.warning("停机:进行中任务将标记中断,重启后由 recover 兜底等待人工重试")
        if scheduler:
            scheduler.shutdown(wait=False)
        conn.close()

    app = FastAPI(title="StarDissect", lifespan=lifespan)
    app.include_router(routes.router)
    app.include_router(routes.public)
    dist = config.web_dist()
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="spa")
    return app


def db_path() -> Path:
    return config.db_path()


def _seed_settings() -> None:
    conn = connect(config.db_path())
    # .env → settings 表:仅补缺,界面设置始终优先(REQ-CFG-001)
    for env_key, setting_key in config.ENV_SEED_MAP.items():
        value = os.environ.get(env_key)
        if not value:
            continue
        exists = conn.execute("SELECT 1 FROM settings WHERE key=?", (setting_key,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO settings(key, value) VALUES (?,?)", (setting_key, value))
    conn.commit()
    conn.close()


# uvicorn 入口:uvicorn app.main:app(仓库根运行)
app = create_app()
