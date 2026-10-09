# 应用装配:单进程 FastAPI(ADR-0001);调度+队列随 lifespan 启动(ADR-0004)
import asyncio
import contextlib
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.agents import runner
from app.api import routes
from app.db import connect, init_db
from app.tasks import queue


async def _queue_loop():
    # 服务循环:独立连接(写者隔离,审查 T-05);无任务时间歇;异常兜底防停摆
    conn = connect(config.db_path())
    while True:
        try:
            stepped = await asyncio.to_thread(queue.step, conn, _execute)
            await asyncio.sleep(0.2 if stepped else 2.0)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 —— 单次失败不杀死循环
            await asyncio.sleep(5.0)


def _execute(task_id: int):
    # 同步桥:工作线程独立连接;watcher 轮询终止请求(REQ-TASK-002)
    conn = connect(config.db_path())
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    repo = conn.execute("SELECT * FROM repos WHERE id=?", (task["repo_id"],)).fetchone()

    async def _run():
        run = asyncio.ensure_future(runner.run_task(conn, task, repo))
        term = asyncio.ensure_future(_watch_terminate(run, task_id))
        try:
            return await run
        finally:
            term.cancel()

    return asyncio.run(_run())


async def _watch_terminate(run, task_id: int):
    while True:
        if task_id in queue.TERMINATE_REQUESTS:
            queue.TERMINATE_REQUESTS.discard(task_id)
            run.cancel()
            return
        await asyncio.sleep(0.5)


def create_app(data_dir: str | None = None, workers: bool = True) -> FastAPI:
    if data_dir:
        import os

        os.environ["STARDISSECT_DATA"] = data_dir
    config.load_env()
    init_db(config.db_path())
    conn = connect(config.db_path())
    _seed_settings(conn)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        queue.recover(conn)  # 启动恢复(REQ-TASK-006)
        scheduler = None
        loop_task = None
        if workers:
            loop_task = asyncio.create_task(_queue_loop())
            scheduler = AsyncIOScheduler()
            async def _daily_sync():
                # 定时同步(REQ-SYNC-001);进行中则跳过本轮(REQ-SYNC-002 合并语义)
                row = conn.execute("SELECT value FROM settings WHERE key='github_token'").fetchone()
                flag = conn.execute("SELECT value FROM settings WHERE key='syncing'").fetchone()
                if row and (flag is None or flag["value"] != "1"):
                    from app.sync import syncer

                    with contextlib.suppress(Exception):
                        await syncer.sync_star(conn, row["value"])
            scheduler.add_job(_daily_sync, "cron", hour=3, minute=17)
            scheduler.start()
        yield
        if loop_task:
            loop_task.cancel()
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="StarDissect", lifespan=lifespan)
    app.state.conn = conn
    app.include_router(routes.router)
    app.include_router(routes.public)
    dist = config.web_dist()
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="spa")
    return app


def _seed_settings(conn) -> None:
    # .env → settings 表:仅补缺,界面设置始终优先(REQ-CFG-001)
    for env_key, setting_key in config.ENV_SEED_MAP.items():
        value = os.environ.get(env_key)
        if not value:
            continue
        exists = conn.execute("SELECT 1 FROM settings WHERE key=?", (setting_key,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO settings(key, value) VALUES (?,?)", (setting_key, value))
    conn.commit()


# uvicorn 入口:uvicorn app.main:app(仓库根运行)
app = create_app()
