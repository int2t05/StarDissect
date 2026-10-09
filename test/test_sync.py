# S6 同步器测试:star 落库/过滤/取消标记/入队联动(真实数据结构;网络调用走门控)
import os

import pytest

from app.db import connect, init_db
from app.search import indexer
from app.sync import syncer


@pytest.fixture()
def conn(tmp_path):
    p = tmp_path / "app.db"
    init_db(p)
    return connect(p)


def _star(full_name, github_id, fork=False, archived=False, starred_at="2026-10-01T00:00:00Z"):
    return {"starred_at": starred_at, "repo": {"id": github_id, "full_name": full_name, "fork": fork, "archived": archived, "description": "d", "language": "Python", "default_branch": "main"}}


def test_apply_stars_inserts_and_enqueues(conn):
    counts = syncer.apply_stars(conn, [_star("o/good", 1)])
    assert counts == {"added": 1, "removed": 0, "skipped": 0}
    repo = conn.execute("SELECT * FROM repos").fetchone()
    assert repo["status"] == "已收录"
    task = conn.execute("SELECT * FROM tasks").fetchone()
    assert task["priority"] == 0  # 新 star 优先(REQ-TASK-001)


def test_apply_stars_skips_fork_and_archived(conn):
    counts = syncer.apply_stars(conn, [_star("o/f", 1, fork=True), _star("o/a", 2, archived=True)])
    assert counts["skipped"] == 2
    assert conn.execute("SELECT COUNT(*) c FROM repos").fetchone()["c"] == 0


def test_apply_stars_marks_unstar_without_delete(conn):
    syncer.apply_stars(conn, [_star("o/good", 1)])
    counts = syncer.apply_stars(conn, [_star("o/other", 2)])  # o/good 消失
    assert counts["removed"] == 1
    row = conn.execute("SELECT unstarred FROM repos WHERE github_id=1").fetchone()
    assert row["unstarred"] == 1  # 标记不删(REQ-SYNC-001)


def test_apply_stars_restars_and_no_duplicate_task(conn):
    syncer.apply_stars(conn, [_star("o/good", 1)])
    syncer.apply_stars(conn, [_star("o/good", 1)])  # 再同步:不重复入库/入队
    assert conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"] == 1


def test_excluded_repo_not_enqueued(conn):
    syncer.apply_stars(conn, [_star("o/good", 1)])
    conn.execute("UPDATE repos SET excluded=1")
    conn.execute("DELETE FROM tasks")
    conn.commit()
    syncer.apply_stars(conn, [_star("o/other", 2), _star("o/good", 1)])
    repos = conn.execute("SELECT COUNT(*) c FROM repos WHERE excluded=1").fetchone()
    assert repos["c"] == 1


@pytest.mark.skipif(
    not (os.environ.get("STARDISSECT_IT_GH") == "1" and os.environ.get("GITHUB_TOKEN")),
    reason="GitHub 端到端为真实调用:需 STARDISSECT_IT_GH=1 与 GITHUB_TOKEN(CLAUDE.md:无 mock)",
)
async def test_sync_star_real(tmp_path):
    from app.db import init_db

    db = tmp_path / "app.db"
    init_db(db)
    conn = connect(db)
    counts = await syncer.sync_star(conn, os.environ["GITHUB_TOKEN"])
    assert counts["added"] > 0
    run = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    assert run["finished_at"] is not None
