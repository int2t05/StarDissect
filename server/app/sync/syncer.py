# 同步器(ADR-0003):star 列表全量拉取(gidgethub+httpx)、fork/archive 过滤、入库/取消标记
# REQ-SYNC-001…003:取消 star 标记不删数据;fork/archive 不入库(OPN-05:手动例外后续版本)
import logging
import sqlite3
from datetime import datetime, timezone

import httpx
from gidgethub import httpx as gh_httpx

from app.search import indexer
from app.tasks.queue import DuplicateTask, enqueue, task_limits

logger = logging.getLogger("stardissect.sync")

STAR_ACCEPT = "application/vnd.github.star+json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def apply_stars(conn: sqlite3.Connection, items: list[dict]) -> dict:
    """落库一轮 star 全量数据(结构=GitHub /user/starred 项:{starred_at, repo});
    新入库仓库自动排队分析(新 star 优先,REQ-TASK-001)。返回计数。"""
    counts = {"added": 0, "removed": 0, "skipped": 0}
    limits = task_limits(conn)
    seen = set()
    for item in items:
        repo = item["repo"]
        if repo.get("fork") or repo.get("archived"):
            counts["skipped"] += 1
            continue
        seen.add(repo["full_name"])
        row = conn.execute("SELECT id, unstarred FROM repos WHERE github_id=?", (repo["id"],)).fetchone()
        if row is None:
            cur = conn.execute(
                "INSERT INTO repos(github_id, full_name, description, language, default_branch, status, starred_at)"
                " VALUES (?,?,?,?,?,'已收录',?)",
                (repo["id"], repo["full_name"], repo.get("description"), repo.get("language"),
                 repo.get("default_branch") or "main", item.get("starred_at")),
            )
            indexer.index_repo(conn, cur.lastrowid)  # 仓库元信息入检索域(REQ-SRCH-001)
            counts["added"] += 1
            _enqueue_analysis(conn, repo["id"], priority=0, limits=limits)
        elif row["unstarred"]:
            conn.execute("UPDATE repos SET unstarred=0, updated_at=? WHERE id=?", (_now(), row["id"]))
            counts["added"] += 1
            _enqueue_analysis(conn, repo["id"], priority=0, limits=limits)
    for row in conn.execute("SELECT id, full_name FROM repos WHERE unstarred=0").fetchall():
        if row["full_name"] not in seen:
            conn.execute("UPDATE repos SET unstarred=1, updated_at=? WHERE id=?", (_now(), row["id"]))
            counts["removed"] += 1
    conn.commit()
    logger.info("star 落库:新增 %s 取消 %s 跳过 %s", counts["added"], counts["removed"], counts["skipped"])
    return counts


def _enqueue_analysis(conn, repo_id: int, priority: int, limits: dict) -> None:
    # 复用队列唯一入口:去重/排除校验一致(B6);重复入队静默忽略
    try:
        enqueue(conn, repo_id, "analyze", priority=priority, turn_limit=limits["turn_limit"], time_limit_sec=limits["time_limit_sec"])
    except DuplicateTask:
        pass
    except Exception as e:  # noqa: BLE001 —— 单仓库入队失败不阻塞整轮同步
        logger.warning("仓库 %s 入队失败: %s", repo_id, e)


async def sync_star(conn: sqlite3.Connection, token: str) -> dict:
    """全量拉取本人 star 列表并入库;限流记跳过待下轮,其他失败如实记录后上抛(REQ-SYNC-001)。"""
    run_id = conn.execute("INSERT INTO sync_runs(started_at) VALUES (?)", (_now(),)).lastrowid
    conn.commit()
    try:
        async with httpx.AsyncClient() as session:
            # 签名:GitHubAPI(client, requester, *, oauth_token=...)
            gh = gh_httpx.GitHubAPI(session, "stardissect", oauth_token=token)
            items = [item async for item in gh.getiter("/user/starred", accept=STAR_ACCEPT)]
        counts = apply_stars(conn, items)
    except httpx.HTTPStatusError as e:
        # 接口限流/凭据配额:本轮记跳过,已有数据保留,等待下轮(REQ-SYNC-001)
        if e.response.status_code in (403, 429):
            counts = {"added": 0, "removed": 0, "skipped": 1}
            conn.execute(
                "UPDATE sync_runs SET finished_at=?, skipped=1 WHERE id=?", (_now(), run_id)
            )
            conn.commit()
            logger.warning("同步被限流(%s),本轮跳过", e.response.status_code)
            return counts
        conn.execute("UPDATE sync_runs SET finished_at=?, failed=1 WHERE id=?", (_now(), run_id))
        conn.commit()
        raise
    except Exception:
        # 失败如实记录,游标不动(ADR-0003)
        conn.execute("UPDATE sync_runs SET finished_at=?, failed=1 WHERE id=?", (_now(), run_id))
        conn.commit()
        raise
    conn.execute(
        "UPDATE sync_runs SET finished_at=?, added=?, removed=?, skipped=? WHERE id=?",
        (_now(), counts["added"], counts["removed"], counts["skipped"], run_id),
    )
    conn.commit()
    return counts
