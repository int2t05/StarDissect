# 同步器(ADR-0003):star 列表全量拉取(gidgethub+httpx)、fork/archive 过滤、入库/取消标记
# REQ-SYNC-001…003:取消 star 标记不删数据;fork/archive 不入库(OPN-05:手动例外后续版本)
import sqlite3
from datetime import datetime, timezone

import httpx
from gidgethub import httpx as gh_httpx

STAR_ACCEPT = "application/vnd.github.star+json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def apply_stars(conn: sqlite3.Connection, items: list[dict]) -> dict:
    """落库一轮 star 全量数据(结构=GitHub /user/starred 项:{starred_at, repo});
    新入库仓库自动排队分析(新 star 优先,REQ-TASK-001)。返回计数。"""
    counts = {"added": 0, "removed": 0, "skipped": 0, "failed": 0}
    limits = _task_limits(conn)
    seen = set()
    for item in items:
        repo = item["repo"]
        if repo.get("fork") or repo.get("archived"):
            counts["skipped"] += 1
            continue
        seen.add(repo["full_name"])
        row = conn.execute("SELECT id, unstarred FROM repos WHERE github_id=?", (repo["id"],)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO repos(github_id, full_name, description, language, default_branch, status, starred_at)"
                " VALUES (?,?,?,?,?,'已收录',?)",
                (repo["id"], repo["full_name"], repo.get("description"), repo.get("language"),
                 repo.get("default_branch") or "main", item.get("starred_at")),
            )
            counts["added"] += 1
            _enqueue_analysis(conn, repo["full_name"], priority=0, limits=limits)
        elif row["unstarred"]:
            conn.execute("UPDATE repos SET unstarred=0, updated_at=? WHERE id=?", (_now(), row["id"]))
            counts["added"] += 1
            _enqueue_analysis(conn, repo["full_name"], priority=0, limits=limits)
    for row in conn.execute("SELECT id, full_name FROM repos WHERE unstarred=0").fetchall():
        if row["full_name"] not in seen:
            conn.execute("UPDATE repos SET unstarred=1, updated_at=? WHERE id=?", (_now(), row["id"]))
            counts["removed"] += 1
    conn.commit()
    return counts


def _task_limits(conn) -> dict:
    s = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {"turn_limit": int(s.get("turn_limit", "30")), "time_limit_sec": int(s.get("time_limit_sec", "1800"))}


def _enqueue_analysis(conn, full_name: str, priority: int, limits: dict) -> None:
    from app.tasks import queue

    repo = conn.execute("SELECT id, excluded FROM repos WHERE full_name=?", (full_name,)).fetchone()
    if repo is None or repo["excluded"]:
        return
    busy = conn.execute("SELECT 1 FROM tasks WHERE repo_id=? AND status IN ('排队','进行')", (repo["id"],)).fetchone()
    if busy:
        return
    conn.execute(
        "INSERT INTO tasks(repo_id, kind, status, priority, turn_limit, time_limit_sec)"
        " VALUES (?, 'analyze', '排队', ?, ?, ?)",
        (repo["id"], priority, limits["turn_limit"], limits["time_limit_sec"]),
    )


async def sync_star(conn: sqlite3.Connection, token: str) -> dict:
    """全量拉取本人 star 列表并入库;失败不写完成态,凭据/限流异常向上抛(REQ-SYNC-001)。"""
    run_id = conn.execute("INSERT INTO sync_runs(started_at) VALUES (?)", (_now(),)).lastrowid
    conn.commit()
    try:
        async with httpx.AsyncClient() as session:
            gh = gh_httpx.GitHubAPI("stardissect", oauth_token=token, session=session)
            items = [item async for item in gh.getiter("/user/starred", accept=STAR_ACCEPT)]
        counts = apply_stars(conn, items)
    except Exception:
        conn.commit()
        raise
    conn.execute(
        "UPDATE sync_runs SET finished_at=?, added=?, removed=?, skipped=?, failed=? WHERE id=?",
        (_now(), counts["added"], counts["removed"], counts["skipped"], counts["failed"], run_id),
    )
    conn.commit()
    return counts
