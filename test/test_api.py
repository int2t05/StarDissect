# API 测试:真实 app + 真实 SQLite(tmp 数据目录),httpx ASGI 直连,无 mock
import pytest
from httpx import ASGITransport, AsyncClient

from app.db import connect
from app.main import create_app
from app.search import indexer


@pytest.fixture()
async def client(tmp_path):
    app = create_app(data_dir=str(tmp_path / "data"), workers=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c, app.router.lifespan_context(app):
        # 连接随每请求独立;测试自持连接做断言与种子
        conn = connect(tmp_path / "data" / "app.db")
        yield c, conn
        conn.close()


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
    r = await c.patch("/api/settings", json={"ai_api_key": "sk-1234567890abcd", "turn_limit": "25"})
    assert r.status_code == 200
    r = await c.get("/api/settings")
    assert r.json()["ai_api_key"] == "…abcd"  # 密钥只回尾号(REQ-CFG-001)
    assert r.json()["turn_limit"] == "25"
    assert "sk-1234567890abcd" not in r.text


async def test_settings_github_token_validated(client):
    # AC-027:token 校验失败不影响其他项保存,且无效 token 不落库
    c, conn = client
    r = await c.patch("/api/settings", json={"github_token": "ghp_invalid_token_xxx", "turn_limit": "18"})
    assert r.status_code == 422
    assert conn.execute("SELECT value FROM settings WHERE key='turn_limit'").fetchone()["value"] == "18"


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
    # 掩码「…尾号」原样提交不得覆盖服务端真值;内部键不外吐
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


async def test_healthz(client):
    # 探活端点:库可读即健康
    c, _ = client
    r = await c.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


async def test_entries_aggregated_with_state_filter(client):
    # G1:阅读中心条目聚合,单查询含仓库信息与已读/收藏;服务端筛选(REQ-READ-006)
    c, conn = client
    await _seed_report(conn)
    await c.patch("/api/reports/1/state", json={"read": True, "favorited": True})
    r = await c.get("/api/entries")
    assert r.json() and r.json()[0]["full_name"] == "o/demo"
    r = await c.get("/api/entries", params={"state": "unread"})
    assert r.json() == []
    r = await c.get("/api/entries", params={"state": "favorited"})
    assert len(r.json()) == 1


async def test_repo_categories_multi_assign_and_filter(client):
    # REQ-CLS-006:领域类别(大方向)集中管理,一仓库可归多类;独立于主类型与标签
    c, conn = client
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (1, 11, 'o/demo', '已分类')")
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (2, 22, 'o/other', '已分类')")
    conn.commit()

    r = await c.post("/api/categories", json={"name": "前端"})
    assert r.status_code == 200
    web_id = r.json()["id"]
    assert (await c.post("/api/categories", json={"name": "前端"})).status_code == 409  # 重名拒绝
    assert (await c.post("/api/categories", json={"name": " "})).status_code == 422     # 空名拒绝

    # 一库多类;归类时类别不存在则自动创建
    await c.post("/api/repos/1/categories", json={"name": "前端"})
    await c.post("/api/repos/1/categories", json={"name": "AI 工具"})
    await c.post("/api/repos/2/categories", json={"name": "前端"})

    detail = (await c.get("/api/repos/1")).json()
    assert [x["name"] for x in detail["categories"]] == ["AI 工具", "前端"]

    cats = {x["name"]: x for x in (await c.get("/api/categories")).json()}
    assert cats["前端"]["repos"] == 2 and cats["AI 工具"]["repos"] == 1

    # 列表按类别过滤,且每行附带类别
    r = (await c.get("/api/repos", params={"category": web_id})).json()
    assert {x["full_name"] for x in r} == {"o/demo", "o/other"}
    ai_id = cats["AI 工具"]["id"]
    r = (await c.get("/api/repos", params={"category": ai_id})).json()
    assert [x["full_name"] for x in r] == ["o/demo"]
    assert {"id": ai_id, "name": "AI 工具"} in r[0]["categories"]

    # 重命名传播到仓库视图
    assert (await c.patch(f"/api/categories/{web_id}", json={"name": "Web"})).status_code == 200
    detail = (await c.get("/api/repos/1")).json()
    assert "Web" in [x["name"] for x in detail["categories"]]

    # 解除关联不删类别;删除类别解除全部关联
    assert (await c.delete(f"/api/repos/1/categories/{ai_id}")).status_code == 200
    detail = (await c.get("/api/repos/1")).json()
    assert [x["name"] for x in detail["categories"]] == ["Web"]
    assert (await c.delete(f"/api/categories/{web_id}")).status_code == 200
    assert (await c.get("/api/repos/1")).json()["categories"] == []
    assert conn.execute("SELECT COUNT(*) c FROM repo_categories").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"] == 1  # AI 工具仍在


async def test_reading_mosaic_counts_and_category_filter(client):
    # 阅读中心拼图:类别仓库数、/api/entries 类别过滤、未分类与全部的仓库口径(REQ-CLS-006)
    c, conn = client
    await _seed_report(conn)  # o/demo:repo 1,一篇未读报告
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (2, 22, 'o/other', '可阅读')")
    conn.commit()
    from app.agents.runner import ReportDraft, Section

    from app.agents import runner
    runner.persist_report(conn, 2, task_id=None, commit_anchor="b" * 40, draft=ReportDraft(
        sections=[Section(title="概览", body="另一篇。")], knowledge_points=[]))
    conn.commit()
    await c.patch("/api/reports/2/state", json={"read": True})

    await c.post("/api/repos/1/categories", json={"name": "AI"})
    cats = (await c.get("/api/categories")).json()
    assert cats[0]["name"] == "AI" and cats[0]["repos"] == 1

    ov = (await c.get("/api/reading/overview")).json()
    assert ov["total"] == {"repos": 2}
    assert ov["uncategorized"] == {"repos": 1}

    ai_id = cats[0]["id"]
    r = (await c.get("/api/entries", params={"category": ai_id})).json()
    assert [x["full_name"] for x in r] == ["o/demo"]
    r = (await c.get("/api/entries", params={"category": -1})).json()
    assert [x["full_name"] for x in r] == ["o/other"]  # 未分类
    r = (await c.get("/api/entries", params={"category": ai_id, "state": "favorited"})).json()
    assert r == []


# ---------- 归档(仓库级 + 报告级)与更新检测 ----------

async def test_repo_archive_filter_and_refusal(client):
    # 仓库归档:默认视图隐藏、归档页签可见、拒绝入队、恢复可逆
    c, conn = client
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (1, 11, 'o/demo', '已分类')")
    conn.commit()
    assert (await c.patch("/api/repos/1", json={"archived": True})).status_code == 200
    assert (await c.get("/api/repos", params={"filter": "all"})).json() == []
    assert (await c.get("/api/repos", params={"filter": "active"})).json() == []
    arch = (await c.get("/api/repos", params={"filter": "archived"})).json()
    assert [x["full_name"] for x in arch] == ["o/demo"]
    r = await c.post("/api/repos/1/analyze")
    assert r.status_code == 400 and "归档" in r.json()["detail"]  # 拒绝新分析任务
    assert (await c.patch("/api/repos/1", json={"archived": False})).status_code == 200
    assert [x["full_name"] for x in (await c.get("/api/repos", params={"filter": "all"})).json()] == ["o/demo"]
    assert (await c.post("/api/repos/1/analyze")).status_code == 200


async def test_report_archive_entries_rss_and_counts(client):
    # 报告归档:阅读中心默认隐藏、state=archived 可见、RSS 与拼图计数排除;恢复可逆
    c, conn = client
    vid = await _seed_report(conn)
    await c.post("/api/repos/1/categories", json={"name": "AI"})
    assert (await c.patch(f"/api/reports/{vid}/state", json={"archived": True})).status_code == 200
    assert (await c.get("/api/entries")).json() == []
    arch = (await c.get("/api/entries", params={"state": "archived"})).json()
    assert len(arch) == 1 and arch[0]["archived"] == 1
    assert b"<entry>" not in (await c.get("/rss.xml")).content
    ov = (await c.get("/api/reading/overview")).json()
    assert ov["total"] == {"repos": 0}  # 全部=有可见报告的仓库数;报告归档后归零
    cats = (await c.get("/api/categories")).json()
    assert cats[0]["repos"] == 1  # 类别拼图按仓库数:仓库仍在类别,不随报告归档消失
    await c.patch(f"/api/reports/{vid}/state", json={"archived": False})  # 恢复
    assert len((await c.get("/api/entries")).json()) == 1
    assert b"<entry>" in (await c.get("/rss.xml")).content


async def test_repo_archive_hides_reports_and_counts(client):
    # 仓库归档:报告随仓隐藏(任一归档即隐藏),计数与 RSS 同步排除;恢复回归
    c, conn = client
    await _seed_report(conn)
    await c.post("/api/repos/1/categories", json={"name": "AI"})
    assert (await c.patch("/api/repos/1", json={"archived": True})).status_code == 200
    assert (await c.get("/api/entries")).json() == []
    ov = (await c.get("/api/reading/overview")).json()
    assert ov["total"] == {"repos": 0}
    cats = (await c.get("/api/categories")).json()
    assert cats[0]["repos"] == 0
    assert b"<entry>" not in (await c.get("/rss.xml")).content
    await c.patch("/api/repos/1", json={"archived": False})
    assert len((await c.get("/api/entries")).json()) == 1


async def test_updates_check_guards(client):
    # 更新检测护栏:未配 token 400;无报告仓库 400(真实网络调用不在此覆盖)
    c, conn = client
    conn.execute("DELETE FROM settings WHERE key='github_token'")
    conn.commit()
    r = await c.post("/api/repos/1/updates/check")
    assert r.status_code == 400 and "token" in r.json()["detail"]
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('github_token', 't')")
    conn.execute("INSERT INTO repos(id, github_id, full_name, status) VALUES (2, 22, 'o/none', '已分类')")
    conn.commit()
    r = await c.post("/api/repos/2/updates/check")
    assert r.status_code == 400 and "报告" in r.json()["detail"]


async def test_report_hard_delete_requires_archive_and_cascades(client):
    # 归档后可硬删除(DEC-06 修订):未归档 400;删除连带章节/知识点/进度/FTS,单事务
    c, conn = client
    vid = await _seed_report(conn)
    await c.put(f"/api/reports/{vid}/progress", json={"anchor_seq": 1, "top_percent": 10, "bottom_percent": 10})
    # 未归档拒绝删除
    r = await c.delete(f"/api/reports/{vid}")
    assert r.status_code == 400 and "归档" in r.json()["detail"]
    # 归档后删除
    await c.patch(f"/api/reports/{vid}/state", json={"archived": True})
    assert (await c.delete(f"/api/reports/{vid}")).status_code == 200
    assert conn.execute("SELECT COUNT(*) c FROM report_versions").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM report_sections").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM knowledge_points").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM reading_progress").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM report_fts").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM knowledge_fts").fetchone()["c"] == 0
    assert (await c.get(f"/api/reports/{vid}")).status_code == 404
    assert (await c.get("/api/search", params={"q": "模块边界"})).json() == []
    # 删除后再次删除:404
    assert (await c.delete(f"/api/reports/{vid}")).status_code == 404


async def test_report_delete_invalidates_behind_state(client):
    # 删除的版本即落后检测锚点时:behind 三列失效清空
    c, conn = client
    vid = await _seed_report(conn)
    from app.sync import updates

    updates.apply_behind(conn, 1, 5)
    conn.commit()
    await c.patch(f"/api/reports/{vid}/state", json={"archived": True})
    assert (await c.delete(f"/api/reports/{vid}")).status_code == 200
    row = conn.execute("SELECT behind_count, behind_checked_at FROM repos WHERE id=1").fetchone()
    assert row["behind_count"] is None and row["behind_checked_at"] is None
