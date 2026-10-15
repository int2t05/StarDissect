# 更新检测(手动建议式):检测报告锚点落后远端默认分支 HEAD 的 commits 数并存库,
# 前端展示「建议重分析」提示;绝不自动入队重分析(SCP-02/DEC-06)
import logging
import sqlite3
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("stardissect.updates")

_COMPARE_URL = "https://api.github.com/repos/{full_name}/compare/{anchor}...{branch}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _compare_behind(full_name: str, anchor: str, default_branch: str, token: str) -> int | None:
    """compare 接口取 ahead_by(anchor...default_branch),即落后远端默认分支的提交数;
    锚点失效(404/422)返回 None。plain httpx + Bearer 模式(镜像 agents/tools.py fetch_github)。"""
    url = _COMPARE_URL.format(full_name=full_name, anchor=anchor, branch=default_branch)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
    if r.status_code in (404, 422):
        return None  # 锚点 commit 已被 force-push 清除或仓库不可见:落后数失效
    r.raise_for_status()
    return int(r.json()["ahead_by"])


def apply_behind(conn: sqlite3.Connection, repo_id: int, behind: int | None) -> None:
    """落库单仓库检测结果;None=锚点失效 → 清空三列(语义=未检测)。不提交,调用方统一事务。"""
    if behind is None:
        conn.execute(
            "UPDATE repos SET behind_count=NULL, behind_checked_at=NULL, behind_anchor=NULL WHERE id=?",
            (repo_id,),
        )
    else:
        conn.execute(
            "UPDATE repos SET behind_count=?, behind_checked_at=?, behind_anchor="
            "(SELECT commit_anchor FROM report_versions WHERE repo_id=? ORDER BY version_no DESC LIMIT 1)"
            " WHERE id=?",
            (behind, _now(), repo_id, repo_id),
        )


async def check_repo(conn: sqlite3.Connection, token: str, repo_id: int) -> dict:
    """单仓库检测(详情页手动「检查更新」):无报告版本拒绝(ValueError→API 400)。返回 behind 字典。"""
    repo = conn.execute("SELECT full_name, default_branch FROM repos WHERE id=?", (repo_id,)).fetchone()
    if repo is None:
        raise LookupError(f"仓库不存在: {repo_id}")
    anchor = conn.execute(
        "SELECT commit_anchor FROM report_versions WHERE repo_id=? ORDER BY version_no DESC LIMIT 1",
        (repo_id,),
    ).fetchone()
    if anchor is None:
        raise ValueError("仓库尚无报告,无可检测锚点")
    behind = await _compare_behind(repo["full_name"], anchor["commit_anchor"], repo["default_branch"] or "main", token)
    apply_behind(conn, repo_id, behind)
    conn.commit()
    return {"repo_id": repo_id, "behind_count": behind, "checked_at": _now() if behind is not None else None}


async def check_all(conn: sqlite3.Connection, token: str) -> dict:
    """遍历检测:未归档且有报告版本的仓库。403/429 限流即停(保留已完成部分),
    锚点失效清空该仓字段,单仓库网络异常记日志继续。返回统计。"""
    repos = conn.execute(
        """SELECT r.id FROM repos r
           WHERE r.archived=0 AND EXISTS (SELECT 1 FROM report_versions v WHERE v.repo_id=r.id)"""
    ).fetchall()
    checked = stale = failed = 0
    for row in repos:
        try:
            result = await check_repo(conn, token, row["id"])
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (403, 429):
                logger.warning("更新检测被限流(%s),本轮停止,已完成 %s 个", code, checked)
                break
            logger.warning("更新检测失败 repo=%s status=%s", row["id"], code)
            failed += 1
            continue
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("更新检测失败 repo=%s: %s", row["id"], e)
            failed += 1
            continue
        checked += 1
        if result["behind_count"] is None:
            stale += 1  # 锚点失效:已清空,不计落后
    logger.info("更新检测完成:检测 %s(锚点失效 %s)失败 %s", checked, stale, failed)
    return {"checked": checked, "stale": stale, "failed": failed}
