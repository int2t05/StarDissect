# S6 API 测试:真实 app + 真实 SQLite(tmp 数据目录),httpx ASGI 直连,无 mock
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.search import indexer


@pytest.fixture()
async def client(tmp_path):
    app = create_app(data_dir=str(tmp_path / "data"), workers=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c, app.router.lifespan_context(app):
        yield c, app.state.conn


async def _seed_report(conn):
    from app.agents.runner import ReportDraft, Section, KnowledgePoint
    from app.agents import runner

    conn.execute("INSERT INTO repos(id, github_id, full_name, description, status) VALUES (1, 11, 'o/demo', '演示', '可阅读')")
    conn.commit()
    draft = ReportDraft(
        sections=[Section(title="系统设计", body="模块边界清晰。\n\n> [source] core.py:1")],
        knowledge_points=[KnowledgePoint(statement="模块边界清晰,扩展点在中间件", evidence=[])],
    )
    return runner.persist_report(conn, 1, task_id=None, commit_anchor="a" * 40, draft=draft)


async def test_settings_secret_masked(client):
    c, conn = client
    r = await c.patch("/api/settings", json={"github_token": "ghp_1234567890abcd", "turn_limit": "25"})
    assert r.status_code == 200
    r = await c.get("/api/settings")
    assert r.json()["github_token"] == "…abcd"  # 密钥只回尾号(REQ-CFG-001)
    assert r.json()["turn_limit"] == "25"
    assert "ghp_1234567890abcd" not in r.text


async def test_sync_requires_token_and_reports_status(client):
    c, conn = client
    # 无凭据→400(REQ-SYNC-001 异常);删除种子 token 模拟未配置环境
    conn.execute("DELETE FROM settings WHERE key='github_token'")
    conn.commit()
    r = await c.post("/api/sync")
    assert r.status_code == 400
    r = await c.get("/api/sync")
    assert r.json() == {"never": True}


async def test_settings_masked_value_not_overwritten(client):
    # 审查 T-02:掩码「…尾号」原样提交不得覆盖服务端真值;内部键不外吐
    c, conn = client
    real = "sk-real-secret-9999"
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('ai_api_key', ?)", (real,))
    conn.commit()
    r = await c.get("/api/settings")
    assert r.json()["ai_api_key"] == "…9999"
    assert "syncing" not in r.json() and "queue_paused" not in r.json()
    r = await c.patch("/api/settings", json={"ai_api_key": "…9999", "turn_limit": "20"})
    assert r.status_code == 200
    assert conn.execute("SELECT value FROM settings WHERE key='ai_api_key'").fetchone()["value"] == real
    r = await c.patch("/api/settings", json={"turn_limit": "0"})
    assert r.status_code == 422  # 限额非法值拒存(CFG-002)


async def test_repo_lock_tags_and_detail(client):
    c, conn = client
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (1, 11, 'o/demo', '已分类')")
    conn.execute("INSERT INTO classifications(repo_id, type, reason, confidence, source) VALUES (1, '框架/库/SDK', '初判', '中', 'auto')")
    conn.commit()
    r = await c.post("/api/repos/1/lock", json={"locked": True})
    assert r.json()["locked"] is True
    locked = conn.execute("SELECT locked, source FROM classifications").fetchone()
    assert locked["locked"] == 1 and locked["source"] == "manual_lock"
    r = await c.post("/api/repos/1/tags", json={"name": "架构学习"})
    r = await c.get("/api/repos/1")
    assert "架构学习" in r.json()["tags"]
    r = await c.delete("/api/repos/1/tags/架构学习")
    assert conn.execute("SELECT COUNT(*) c FROM tags").fetchone()["c"] == 0


async def test_analyze_duplicate_conflict_and_cancel(client):
    c, conn = client
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (1, 11, 'o/demo', '已分类')")
    conn.commit()
    r = await c.post("/api/repos/1/analyze")
    assert r.status_code == 200 and r.json()["status"] == "排队"
    r = await c.post("/api/repos/1/analyze")
    assert r.status_code == 409  # 并发防护(REQ-TASK-004)
    r = await c.get("/api/tasks")
    assert r.json()["tasks"][0]["full_name"] == "o/demo"
    task_id = r.json()["tasks"][0]["id"]
    r = await c.patch(f"/api/tasks/{task_id}", json={"priority": 5})
    assert conn.execute("SELECT priority FROM tasks").fetchone()["priority"] == 5
    r = await c.delete(f"/api/tasks/{task_id}")
    assert conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"] == 0


async def test_retry_only_from_failed_states(client):
    c, conn = client
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (1, 11, 'o/demo', '已分类')")
    conn.execute("INSERT INTO tasks(repo_id, kind, status, priority, turn_limit, time_limit_sec) VALUES (1,'analyze','失败',0,30,1800)")
    conn.commit()
    r = await c.post("/api/tasks/1/retry")
    assert r.status_code == 200  # 失败→新任务行(REQ-TASK-004)
    assert conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"] == 2
    conn.execute("UPDATE tasks SET status='完成' WHERE id=1")
    conn.commit()
    r = await c.post("/api/tasks/1/retry")
    assert r.status_code == 400


async def test_progress_high_water_and_reset(client):
    c, conn = client
    vid = await _seed_report(conn)
    r = await c.put(f"/api/reports/{vid}/progress", json={"anchor_seq": 1, "top_percent": 50, "bottom_percent": 60})
    assert r.json()["ok"] is True
    # 旧设备回传旧位置:不回退(REQ-READ-003/UX-27)
    r = await c.put(f"/api/reports/{vid}/progress", json={"anchor_seq": 0, "top_percent": 10, "bottom_percent": 20})
    assert r.json().get("kept") is True
    row = conn.execute("SELECT * FROM reading_progress").fetchone()
    assert row["anchor"] == "1/50.0"
    # 显式重置到开头:零值特判
    r = await c.put(f"/api/reports/{vid}/progress", json={"anchor_seq": 0, "top_percent": 0, "bottom_percent": 0, "reset": True})
    row = conn.execute("SELECT top_percent FROM reading_progress").fetchone()
    assert row["top_percent"] == 0


async def test_report_get_and_export_and_rss(client):
    c, conn = client
    vid = await _seed_report(conn)
    r = await c.get(f"/api/reports/{vid}")
    assert "模块边界清晰" in r.json()["html"] and r.json()["version_no"] == 1
    r = await c.get(f"/api/reports/{vid}/export")
    assert r.text.startswith("---\nrepo: o/demo")  # 元信息(REQ-OUT-001)
    assert "## 系统设计" in r.text and "[source]" in r.text  # 证据块保留
    r = await c.get("/rss.xml")
    assert r.status_code == 200 and b"<entry>" in r.content  # RSS(REQ-OUT-002)


async def test_search_endpoint_groups_and_hits(client):
    c, conn = client
    await _seed_report(conn)
    r = await c.get("/api/search", params={"q": "模块边界"})
    kinds = {h["kind"] for h in r.json()}
    assert "report" in kinds and "knowledge" in kinds
    r = await c.get("/api/search", params={"q": "  "})
    assert r.json() == []
