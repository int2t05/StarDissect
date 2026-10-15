# 同步器测试:star 落库/过滤/取消标记/入队联动(真实数据结构;网络调用走门控)
import os

import pytest

from app.db import connect, init_db
from app.search import indexer
from app.sync import syncer, updates


@pytest.fixture()
def conn(tmp_path):
    p = tmp_path / "app.db"
    init_db(p)
    return connect(p)


def _star(full_name, github_id, fork=False, archived=False, starred_at="2026-10-01T00:00:00Z"):
    return {"starred_at": starred_at, "repo": {"id": github_id, "full_name": full_name, "fork": fork, "archived": archived, "description": "d", "language": "Python", "default_branch": "main"}}


def test_apply_stars_inserts_and_enqueues(conn):
    # github_id 故意远大于本地自增 id:防止入队误用 github_id(部署实测 bug 回归)
    counts = syncer.apply_stars(conn, [_star("o/good", 1179450044)])
    assert counts == {"added": 1, "removed": 0, "skipped": 0}
    repo = conn.execute("SELECT * FROM repos").fetchone()
    assert repo["status"] == "已收录"
    task = conn.execute("SELECT * FROM tasks").fetchone()
    assert task["priority"] == 0  # 新 star 优先(REQ-TASK-001)
    assert task["repo_id"] == repo["id"]


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


# ---------- 更新检测(手动建议式;选取与落库逻辑,compare 走门控真实调用) ----------

def _repo_with_report(conn, repo_id, archived=0):
    conn.execute(
        "INSERT INTO repos(id, full_name, default_branch, status, archived) VALUES (?, 'o/r', 'main', '可阅读', ?)",
        (repo_id, archived),
    )
    conn.execute(
        "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, html, sections_json)"
        " VALUES (?, ?, 1, ?, '<p/>', '[]')",
        (repo_id * 10, repo_id, "a" * 40),
    )
    conn.commit()


def test_apply_behind_persists_and_clears(conn):
    _repo_with_report(conn, 1)
    updates.apply_behind(conn, 1, 7)
    conn.commit()
    row = conn.execute("SELECT behind_count, behind_checked_at, behind_anchor FROM repos WHERE id=1").fetchone()
    assert row["behind_count"] == 7
    assert row["behind_anchor"] == "a" * 40 and row["behind_checked_at"]
    updates.apply_behind(conn, 1, None)  # 锚点失效 → 清空=未检测语义
    conn.commit()
    row = conn.execute("SELECT behind_count, behind_checked_at, behind_anchor FROM repos WHERE id=1").fetchone()
    assert row["behind_count"] is None and row["behind_checked_at"] is None and row["behind_anchor"] is None


async def test_check_repo_requires_report(conn):
    conn.execute("INSERT INTO repos(id, full_name, default_branch, status) VALUES (1, 'o/r', 'main', '已分类')")
    conn.commit()
    with pytest.raises(ValueError):
        await updates.check_repo(conn, "token", 1)  # 无报告无可检测锚点(API 400)


async def test_check_all_selects_active_repos_with_reports(conn, monkeypatch):
    # 选取语义:排除归档仓库与无报告仓库;落后数落库到选中仓库
    _repo_with_report(conn, 1)              # 选中:活跃 + 有报告
    _repo_with_report(conn, 2, archived=1)  # 跳过:已归档
    conn.execute("INSERT INTO repos(id, full_name, status) VALUES (3, 'o/none', '已分类')")
    conn.commit()
    seen = []

    async def fake_compare(full_name, anchor, branch, token):
        seen.append(full_name)
        return 3

    monkeypatch.setattr(updates, "_compare_behind", fake_compare)  # 仅替身网络层,其余真实 DB
    stats = await updates.check_all(conn, "token")
    assert seen == ["o/r"] and stats["checked"] == 1 and stats["stale"] == 0
    row = conn.execute("SELECT behind_count, behind_anchor FROM repos WHERE id=1").fetchone()
    assert row["behind_count"] == 3 and row["behind_anchor"] == "a" * 40


@pytest.mark.skipif(
    not (os.environ.get("STARDISSECT_IT_GH") == "1" and os.environ.get("GITHUB_TOKEN")),
    reason="GitHub 端到端为真实调用:需 STARDISSECT_IT_GH=1 与 GITHUB_TOKEN(CLAUDE.md:无 mock)",
)
async def test_compare_behind_real(tmp_path):
    # 真实 compare:同分支落后 0;不存在的锚点归「失效」(None)
    db = tmp_path / "app.db"
    init_db(db)
    behind = await updates._compare_behind("pallets/click", "main", "main", os.environ["GITHUB_TOKEN"])
    assert behind == 0
    stale = await updates._compare_behind("pallets/click", "0" * 40, "main", os.environ["GITHUB_TOKEN"])
    assert stale is None


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
