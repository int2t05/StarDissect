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


async def _queue_loop(conn):
    # 服务循环:逐个消费任务;无任务时间歇,暂停时同样休眠(REQ-TASK-002)
    while True:
        stepped = await asyncio.to_thread(queue.step, conn, _execute)
        await asyncio.sleep(0.2 if stepped else 2.0)


def _execute(conn, task, repo):
    # 同步桥:队列工作线程中运行 async runner(独立事件循环)
    return asyncio.run(runner.run_task(conn, task, repo))


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
            loop_task = asyncio.create_task(_queue_loop(conn))
            scheduler = AsyncIOScheduler()
            async def _daily_sync():
                token = None
                row = conn.execute("SELECT value FROM settings WHERE key='github_token'").fetchone()
                if row and conn.execute("SELECT value FROM settings WHERE key='syncing'").fetchone() is None:
                    token = row["value"]
                    from app.sync import syncer

                    with contextlib.suppress(Exception):
                        await syncer.sync_star(conn, token)
            scheduler.add_job(_daily_sync, "cron", hour=3, minute=17)  # 每日定时(REQ-SYNC-001)
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


# uvicorn 入口:uvicorn app.main:app(仓库根运行)
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


app = create_app()
