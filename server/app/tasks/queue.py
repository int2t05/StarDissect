# 任务队列(ADR-0004):状态机=docs/PRD.md FIG-02;tasks 表即持久层,重启天然恢复
# step() 处理一个任务,服务端以循环驱动;执行器契约见 step 内注释(REQ-TASK-003 归档语义)
import asyncio
import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger("stardissect.queue")


def task_limits(conn: sqlite3.Connection) -> dict:
    """从设置读取任务限额默认值(公共入口,同步器与 API 共用)。"""
    s = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {"turn_limit": int(s.get("turn_limit", "30")), "time_limit_sec": int(s.get("time_limit_sec", "1800"))}


class DuplicateTask(Exception):
    """同仓库已有排队/进行任务(REQ-TASK-004 并发防护)"""


class ExcludedRepo(Exception):
    """仓库已被排除,不自动分析(REQ-TASK-002)"""


class TaskLimited(Exception):
    """执行器触达轮次/时限上限;partial 标记是否有可发布产出(REQ-TASK-003)"""

    def __init__(self, partial: bool, reason: str):
        super().__init__(reason)
        self.partial = partial
        self.reason = reason


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path):
    from app.db import connect

    return connect(db_path)


def enqueue(conn: sqlite3.Connection, repo_id: int, kind: str, priority: int, turn_limit: int, time_limit_sec: int) -> dict:
    repo = conn.execute("SELECT excluded FROM repos WHERE id=?", (repo_id,)).fetchone()
    if repo is None:
        raise LookupError(f"仓库不存在: {repo_id}")
    if repo["excluded"]:
        raise ExcludedRepo(f"仓库已排除: {repo_id}")
    busy = conn.execute(
        "SELECT 1 FROM tasks WHERE repo_id=? AND status IN ('排队','进行')", (repo_id,)
    ).fetchone()
    if busy:
        raise DuplicateTask(f"仓库 {repo_id} 已有排队/进行任务")
    cur = conn.execute(
        "INSERT INTO tasks(repo_id, kind, status, priority, turn_limit, time_limit_sec)"
        " VALUES (?,?, '排队', ?,?,?)",
        (repo_id, kind, priority, turn_limit, time_limit_sec),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())


def set_paused(conn: sqlite3.Connection, paused: bool) -> None:
    # 暂停/恢复整个队列:settings 键驱动,服务循环与 step 共同消费
    conn.execute(
        "INSERT INTO settings(key, value) VALUES ('queue_paused', ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        ("1" if paused else "0",),
    )
    conn.commit()


def _paused(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT value FROM settings WHERE key='queue_paused'").fetchone()
    return bool(row and row["value"] == "1")


def cancel_pending(conn: sqlite3.Connection, repo_id: int | None = None, task_id: int | None = None) -> int:
    # 取消排队任务:未执行无历史,直接删行(REQ-TASK-002);按仓库或按任务 id
    sql, args = "DELETE FROM tasks WHERE status='排队'", []
    if repo_id is not None:
        sql += " AND repo_id=?"
        args.append(repo_id)
    if task_id is not None:
        sql += " AND id=?"
        args.append(task_id)
    cur = conn.execute(sql, args)
    conn.commit()
    return cur.rowcount


# 分析中终止(REQ-TASK-002):API 侧登记,执行器内的 watcher 轮询并取消;进程重启自然清空
TERMINATE_REQUESTS: set[int] = set()


def request_terminate(conn: sqlite3.Connection, task_id: int) -> bool:
    row = conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None or row["status"] != "进行":
        return False
    TERMINATE_REQUESTS.add(task_id)
    return True


def exclude_repo(conn: sqlite3.Connection, repo_id: int) -> None:
    conn.execute("UPDATE repos SET excluded=1, updated_at=? WHERE id=?", (_now(), repo_id))
    cancel_pending(conn, repo_id)
    conn.commit()


def recover(conn: sqlite3.Connection) -> int:
    # 启动恢复:崩溃残留的「进行」→「中断」,等待人工重试;产物无半成品(事务保证,REQ-TASK-006)
    cur = conn.execute("UPDATE tasks SET status='中断', fail_reason='服务重启中断' WHERE status='进行'")
    conn.commit()
    return cur.rowcount


def step(conn: sqlite3.Connection, executor) -> bool:
    """消费一个任务。executor(task_id) 在独立线程/连接执行重活;归档仍由本连接负责。
    触达限额时 executor raise TaskLimited(partial, reason);取消→「失败·人工终止」;其他异常归「失败」。"""
    if _paused(conn):
        return False
    task = conn.execute(
        "SELECT * FROM tasks WHERE status='排队' ORDER BY priority, id LIMIT 1"
    ).fetchone()
    if task is None:
        return False
    conn.execute(
        "UPDATE tasks SET status='进行', started_at=? WHERE id=?",
        (_now(), task["id"]),
    )
    conn.commit()
    try:
        executor(task["id"])
        status, reason = "完成", None
    except TaskLimited as e:
        status, reason = ("受限完成", e.reason) if e.partial else ("失败", e.reason)
    except asyncio.CancelledError:
        status, reason = "失败", "人工终止"
    except Exception as e:  # noqa: BLE001 —— 归档为失败,原因入 fail_reason 与日志
        status, reason = "失败", f"{type(e).__name__}: {e}"
    logger.info("任务归档 id=%s repo=%s status=%s reason=%s", task["id"], task["repo_id"], status, reason)
    conn.execute(
        "UPDATE tasks SET status=?, fail_reason=?, finished_at=? WHERE id=?",
        (status, reason, _now(), task["id"]),
    )
    conn.commit()
    return True
