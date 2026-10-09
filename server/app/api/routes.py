# REST API 路由(docs/v1.0/tech.md §6;覆盖 REQ-SYNC/CLS/TASK/READ/SRCH/OUT/CFG 的 HTTP 面)
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from feedgen.feed import FeedGenerator

from app.agents import runner
from app.search import indexer
from app.sync import syncer
from app.tasks import queue

router = APIRouter(prefix="/api")
# RSS 面向外部阅读器,挂顶层路径(REQ-OUT-002)
public = APIRouter()

SECRET_KEYS = {"github_token", "ai_api_key", "tavily_api_key", "exa_api_key"}
PUBLIC_KEYS = ["github_user", "ai_model", "ai_base_url", "turn_limit", "time_limit_sec"]
LIMIT_KEYS = {"turn_limit", "time_limit_sec"}  # 限额类:正整数校验(REQ-CFG-002)


# ---------- 同步(REQ-SYNC) ----------

async def _run_sync(app, token: str):
    try:
        await syncer.sync_star(app.state.conn, token)
    finally:
        conn = app.state.conn
        conn.execute("INSERT INTO settings(key, value) VALUES ('syncing','0')"
                     " ON CONFLICT(key) DO UPDATE SET value='0'")
        conn.commit()


@router.post("/sync")
async def start_sync(request: Request, bg: BackgroundTasks):
    conn = request.app.state.conn
    flag = conn.execute("SELECT value FROM settings WHERE key='syncing'").fetchone()
    if flag and flag["value"] == "1":
        return {"started": True, "merged": True}  # 进行中重复触发合并(REQ-SYNC-002)
    token = _setting(conn, "github_token")
    if not token:
        raise HTTPException(400, "未配置 github_token")
    conn.execute("INSERT INTO settings(key, value) VALUES ('syncing','1')"
                 " ON CONFLICT(key) DO UPDATE SET value='1'")
    conn.commit()
    bg.add_task(_run_sync, request.app, token)
    return {"started": True, "merged": False}


@router.get("/sync")
async def sync_status(request: Request):
    row = request.app.state.conn.execute(
        "SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else {"never": True}


def _setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


# ---------- 仓库与分类(REQ-CLS) ----------

@router.get("/repos")
async def list_repos(request: Request, filter: str = "all", q: str = ""):
    conn = request.app.state.conn
    where, args = "WHERE 1=1", []
    if filter == "active":
        where += " AND unstarred=0 AND excluded=0"
    if filter == "unstarred":
        where += " AND unstarred=1"
    if q:
        where += " AND (r.full_name LIKE ? OR r.description LIKE ? OR r.id IN (SELECT repo_id FROM tags WHERE name LIKE ?))"
        args += [f"%{q}%", f"%{q}%", f"%{q}%"]
    rows = conn.execute(
        f"""SELECT r.*, c.type, c.confidence, c.locked,
                   (SELECT COUNT(*) FROM report_versions v WHERE v.repo_id=r.id) AS versions
            FROM repos r LEFT JOIN classifications c ON c.id =
                (SELECT id FROM classifications WHERE repo_id=r.id ORDER BY id DESC LIMIT 1)
            {where} ORDER BY r.updated_at DESC LIMIT 500""",
        args,
    ).fetchall()
    return [dict(x) for x in rows]


@router.get("/repos/{repo_id}")
async def repo_detail(request: Request, repo_id: int):
    conn = request.app.state.conn
    repo = conn.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone()
    if repo is None:
        raise HTTPException(404, "仓库不存在")
    cls = conn.execute(
        "SELECT * FROM classifications WHERE repo_id=? ORDER BY id DESC LIMIT 1", (repo_id,)
    ).fetchone()
    history = conn.execute(
        "SELECT old_type, new_type, reason, created_at FROM classification_history WHERE repo_id=? ORDER BY id DESC", (repo_id,)
    ).fetchall()
    tags = [r["name"] for r in conn.execute("SELECT name FROM tags WHERE repo_id=? ORDER BY name", (repo_id,))]
    versions = conn.execute(
        "SELECT id, version_no, commit_anchor, created_at FROM report_versions WHERE repo_id=? ORDER BY version_no DESC", (repo_id,)
    ).fetchall()
    tasks = conn.execute(
        "SELECT id, kind, status, priority, fail_reason, started_at, finished_at FROM tasks WHERE repo_id=? ORDER BY id DESC", (repo_id,)
    ).fetchall()
    kps = conn.execute(
        "SELECT id, statement, evidence_json, human_edited, revision_note, deleted FROM knowledge_points"
        " WHERE repo_id=? AND deleted=0 ORDER BY id DESC", (repo_id,)
    ).fetchall()
    return {
        "repo": dict(repo), "classification": dict(cls) if cls else None,
        "history": [dict(h) for h in history], "tags": tags,
        "versions": [dict(v) for v in versions], "tasks": [dict(t) for t in tasks],
        "knowledge_points": [dict(k) for k in kps],
    }


@router.patch("/repos/{repo_id}")
async def patch_repo(request: Request, repo_id: int, body: dict):
    conn = request.app.state.conn
    if "excluded" in body:
        if body["excluded"]:
            queue.exclude_repo(conn, repo_id)
        else:
            conn.execute("UPDATE repos SET excluded=0, updated_at=datetime('now') WHERE id=?", (repo_id,))
            conn.commit()
    return {"ok": True}


@router.patch("/reports/{version_id}/state")
async def patch_report_state(request: Request, version_id: int, body: dict):
    # 条目级已读/收藏(REQ-READ-006,键盘 m/f)
    conn = request.app.state.conn
    fields = []
    args = []
    for key in ("read", "favorited"):
        if key in body:
            fields.append(f"{key}=?")
            args.append(1 if body[key] else 0)
    if not fields:
        raise HTTPException(422, "无可更新字段")
    conn.execute(f"UPDATE report_versions SET {','.join(fields)} WHERE id=?", (*args, version_id))
    conn.commit()
    return {"ok": True}


# ---------- 知识点编辑(KP-002:人工修订须标注,不冒充分析结论) ----------

@router.patch("/knowledge_points/{kp_id}")
async def edit_knowledge_point(request: Request, kp_id: int, body: dict):
    conn = request.app.state.conn
    statement = (body.get("statement") or "").strip()
    if not statement:
        raise HTTPException(422, "内容不能为空")
    conn.execute(
        "UPDATE knowledge_points SET statement=?, human_edited=1, revision_note=? WHERE id=?",
        (statement, body.get("note", "人工修订"), kp_id),
    )
    conn.commit()
    indexer.index_knowledge(conn, kp_id)
    conn.commit()
    return {"ok": True}


@router.delete("/knowledge_points/{kp_id}")
async def delete_knowledge_point(request: Request, kp_id: int):
    # 软删除可恢复,不破坏版本完整性(KP-002)
    conn = request.app.state.conn
    conn.execute("UPDATE knowledge_points SET deleted=1 WHERE id=?", (kp_id,))
    conn.commit()
    return {"ok": True}


@router.post("/repos/{repo_id}/lock")
async def lock_classification(request: Request, repo_id: int, body: dict):
    conn = request.app.state.conn
    locked = 1 if body.get("locked") else 0
    row = conn.execute("SELECT id FROM classifications WHERE repo_id=? ORDER BY id DESC LIMIT 1", (repo_id,)).fetchone()
    if row is None:
        raise HTTPException(400, "尚无分类可锁定")
    conn.execute("UPDATE classifications SET locked=? WHERE id=?", (locked, row["id"]))
    if locked:
        conn.execute("UPDATE classifications SET source='manual_lock' WHERE id=?", (row["id"],))
    conn.commit()
    return {"ok": True, "locked": bool(locked)}


@router.post("/repos/{repo_id}/tags")
async def add_tag(request: Request, repo_id: int, body: dict):
    conn = request.app.state.conn
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "标签名不能为空")
    conn.execute("INSERT OR IGNORE INTO tags(repo_id, name) VALUES (?,?)", (repo_id, name))
    conn.commit()
    indexer.index_repo(conn, repo_id)  # 人工标签入检索域(REQ-SRCH-001)
    conn.commit()
    return {"ok": True}


@router.delete("/repos/{repo_id}/tags/{name}")
async def delete_tag(request: Request, repo_id: int, name: str):
    conn = request.app.state.conn
    conn.execute("DELETE FROM tags WHERE repo_id=? AND name=?", (repo_id, name))
    conn.commit()
    indexer.index_repo(conn, repo_id)
    conn.commit()
    return {"ok": True}


@router.post("/repos/{repo_id}/classify")
async def manual_scope(request: Request, repo_id: int, body: dict):
    # 人工选择范围:待处理→已分类并入队(REQ-CLS-002 闭环)
    conn = request.app.state.conn
    if not body.get("type"):
        raise HTTPException(422, "缺少 type")
    if conn.execute("SELECT 1 FROM repos WHERE id=?", (repo_id,)).fetchone() is None:
        raise HTTPException(404, "仓库不存在")
    runner.upsert_classification(conn, repo_id, body["type"], body.get("reason", "人工选择范围"), body.get("confidence", "高"), "manual_scope")
    conn.execute("UPDATE repos SET status='已分类', updated_at=datetime('now') WHERE id=?", (repo_id,))
    conn.commit()
    limits = syncer._task_limits(conn)
    try:
        queue.enqueue(conn, repo_id, "analyze", priority=100, turn_limit=limits["turn_limit"], time_limit_sec=limits["time_limit_sec"])
    except queue.DuplicateTask:
        pass
    return {"ok": True}


@router.post("/repos/{repo_id}/analyze")
async def analyze(request: Request, repo_id: int, body: dict = None):
    conn = request.app.state.conn
    limits = syncer._task_limits(conn)
    priority = 0 if (body or {}).get("priority") == "front" else 100
    kind = "reanalyze" if conn.execute(
        "SELECT 1 FROM report_versions WHERE repo_id=?", (repo_id,)
    ).fetchone() else "analyze"
    try:
        task = queue.enqueue(conn, repo_id, kind, priority=priority,
                             turn_limit=limits["turn_limit"], time_limit_sec=limits["time_limit_sec"])
    except queue.DuplicateTask:
        raise HTTPException(409, "该仓库已有排队/进行任务")
    except queue.ExcludedRepo:
        raise HTTPException(400, "仓库已被排除")
    return task


# ---------- 任务与队列(REQ-TASK) ----------

@router.get("/tasks")
async def list_tasks(request: Request):
    rows = request.app.state.conn.execute(
        """SELECT t.*, r.full_name FROM tasks t JOIN repos r ON r.id=t.repo_id
           ORDER BY CASE t.status WHEN '进行' THEN 0 WHEN '排队' THEN 1 ELSE 2 END, t.id DESC LIMIT 200"""
    ).fetchall()
    paused = _setting(request.app.state.conn, "queue_paused") == "1"
    return {"paused": paused, "tasks": [dict(x) for x in rows]}


@router.patch("/tasks/{task_id}")
async def patch_task(request: Request, task_id: int, body: dict):
    conn = request.app.state.conn
    if "priority" in body:
        conn.execute("UPDATE tasks SET priority=? WHERE id=? AND status='排队'", (int(body["priority"]), task_id))
        conn.commit()
    return {"ok": True}


@router.delete("/tasks/{task_id}")
async def cancel_task(request: Request, task_id: int):
    # 只取消指定排队任务(审查 T-01:此前误删全队列)
    conn = request.app.state.conn
    n = queue.cancel_pending(conn, task_id=task_id)
    if n == 0:
        raise HTTPException(404, "排队任务不存在")
    return {"ok": True, "cancelled": n}


@router.post("/tasks/{task_id}/terminate")
async def terminate_task(request: Request, task_id: int):
    # 终止分析中任务(REQ-TASK-002):登记请求,执行器 watcher 负责取消
    if not queue.request_terminate(request.app.state.conn, task_id):
        raise HTTPException(400, "任务不在进行中")
    return {"ok": True}


@router.post("/tasks/{task_id}/retry")
async def retry_task(request: Request, task_id: int):
    conn = request.app.state.conn
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if task is None:
        raise HTTPException(404, "任务不存在")
    if task["status"] not in ("失败", "受限完成", "中断"):
        raise HTTPException(400, f"状态 {task['status']} 不可重试")
    limits = syncer._task_limits(conn)
    try:
        new = queue.enqueue(conn, task["repo_id"], task["kind"], priority=task["priority"],
                            turn_limit=limits["turn_limit"], time_limit_sec=limits["time_limit_sec"])
    except queue.DuplicateTask:
        raise HTTPException(409, "该仓库已有排队/进行任务")
    return new


@router.post("/queue")
async def set_queue(request: Request, body: dict):
    queue.set_paused(request.app.state.conn, bool(body.get("paused")))
    return {"ok": True}


# ---------- 报告/进度/导出(REQ-RPT/READ/OUT) ----------

@router.get("/repos/{repo_id}/reports")
async def list_versions(request: Request, repo_id: int):
    rows = request.app.state.conn.execute(
        "SELECT id, version_no, commit_anchor, created_at FROM report_versions WHERE repo_id=? ORDER BY version_no DESC",
        (repo_id,),
    ).fetchall()
    return [dict(x) for x in rows]


@router.get("/reports/{version_id}")
async def get_report(request: Request, version_id: int):
    row = request.app.state.conn.execute("SELECT * FROM report_versions WHERE id=?", (version_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "报告版本不存在")
    return {
        "id": row["id"], "repo_id": row["repo_id"], "version_no": row["version_no"],
        "commit_anchor": row["commit_anchor"], "html": row["html"],
        "sections": row["sections_json"], "meta": row["meta_json"], "created_at": row["created_at"],
    }


@router.get("/reports/{version_id}/progress")
async def get_progress(request: Request, version_id: int):
    row = request.app.state.conn.execute(
        "SELECT * FROM reading_progress WHERE report_version_id=?", (version_id,)
    ).fetchone()
    if row is None:
        return {"anchor_seq": 0, "top_percent": 0, "bottom_percent": 0}
    seq, top = _parse_anchor(row["anchor"])
    return {"anchor_seq": seq, "top_percent": top, "bottom_percent": row["bottom_percent"],
            "highest_anchor": row["highest_anchor"]}


@router.put("/reports/{version_id}/progress")
async def put_progress(request: Request, version_id: int, body: dict):
    # 高水位防回退(REQ-READ-003/UX-27);显式重置用零值特判
    conn = request.app.state.conn
    seq, top, bottom = int(body["anchor_seq"]), float(body["top_percent"]), float(body["bottom_percent"])
    if body.get("reset"):
        conn.execute(
            "INSERT INTO reading_progress(report_version_id, anchor, top_percent, bottom_percent, highest_anchor)"
            " VALUES (?, '0/0', 0, 0, '0/0')"
            " ON CONFLICT(report_version_id) DO UPDATE SET anchor='0/0', top_percent=0, bottom_percent=0, updated_at=datetime('now')",
            (version_id,),
        )
        conn.commit()
        return {"ok": True, "reset": True}
    old = conn.execute("SELECT * FROM reading_progress WHERE report_version_id=?", (version_id,)).fetchone()
    old_seq = old_seq_val = 0
    if old and old["anchor"]:
        try:
            old_seq = int(str(old["anchor"]).split("/")[0])
        except ValueError:
            old_seq = 0
    if old and (seq, top) <= (old_seq, old["top_percent"]):
        return {"ok": True, "kept": True}  # 旧位置不回退
    highest = old["highest_anchor"] if old and old["highest_anchor"] else "0/0"
    h_seq, h_top = _parse_anchor(highest)
    if (seq, top) > (h_seq, h_top):
        highest = f"{seq}/{top}"
    conn.execute(
        "INSERT INTO reading_progress(report_version_id, anchor, top_percent, bottom_percent, highest_anchor)"
        " VALUES (?,?,?,?,?)"
        " ON CONFLICT(report_version_id) DO UPDATE SET anchor=excluded.anchor, top_percent=excluded.top_percent,"
        " bottom_percent=excluded.bottom_percent, highest_anchor=excluded.highest_anchor, updated_at=datetime('now')",
        (version_id, f"{seq}/{top}", top, bottom, highest),
    )
    conn.commit()
    return {"ok": True}


def _parse_anchor(text: str) -> tuple[int, float]:
    try:
        s, t = str(text).split("/")
        return int(s), float(t)
    except (ValueError, AttributeError):
        return 0, 0.0


@router.get("/reports/{version_id}/export")
async def export_report(request: Request, version_id: int):
    row = request.app.state.conn.execute(
        """SELECT v.markdown, v.version_no, v.commit_anchor, v.created_at, r.full_name
           FROM report_versions v JOIN repos r ON r.id=v.repo_id WHERE v.id=?""", (version_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "报告版本不存在")
    meta = (
        f"---\nrepo: {row['full_name']}\nversion: v{row['version_no']}\n"
        f"commit: {row['commit_anchor']}\ngenerated_at: {row['created_at']}\n---\n\n"
    )
    return PlainTextResponse(
        meta + row["markdown"],
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{row["full_name"].replace("/", "__")}-v{row["version_no"]}.md"'},
    )


# ---------- 检索(REQ-SRCH) ----------

@router.get("/search")
async def search(request: Request, q: str, limit: int = 20):
    if not q.strip():
        return []
    return indexer.search(request.app.state.conn, q, limit=min(limit, 50))


# ---------- RSS(REQ-OUT-002) ----------

@public.get("/rss.xml")
async def rss(request: Request):
    conn = request.app.state.conn
    fg = FeedGenerator()
    fg.id("stardissect")
    fg.title("StarDissect 报告")
    fg.link(href="/rss.xml")
    rows = conn.execute(
        """SELECT v.id, v.version_no, v.created_at, r.full_name, s.title, s.text_content
           FROM report_versions v JOIN repos r ON r.id=v.repo_id
           LEFT JOIN report_sections s ON s.report_version_id=v.id AND s.seq=0
           ORDER BY v.id DESC LIMIT 50"""
    ).fetchall()
    for row in rows:
        e = fg.add_entry()
        title = f"【{row['full_name']}】v{row['version_no']}"
        e.id(f"/report/{row['id']}")
        e.title(title)
        e.link(href=f"/report/{row['id']}")
        summary = (row["text_content"] or "")[:200]
        e.description(summary)
    return Response(content=fg.atom_str(pretty=True), media_type="application/atom+xml")


# ---------- 设置(REQ-CFG) ----------

@router.get("/settings")
async def get_settings(request: Request):
    # 白名单输出;密钥仅尾号(REQ-CFG-001);内部键(syncing/queue_paused)不外吐
    conn = request.app.state.conn
    allowed = PUBLIC_KEYS + list(SECRET_KEYS)
    out = {}
    for r in conn.execute("SELECT key, value FROM settings"):
        if r["key"] not in allowed:
            continue
        out[r["key"]] = ("…" + r["value"][-4:]) if r["key"] in SECRET_KEYS and r["value"] else r["value"]
    return out


@router.patch("/settings")
async def patch_settings(request: Request, body: dict):
    conn = request.app.state.conn
    allowed = PUBLIC_KEYS + list(SECRET_KEYS)
    for k, v in body.items():
        if k not in allowed:
            raise HTTPException(400, f"未知配置项: {k}")
        text = str(v)
        if k in SECRET_KEYS and text.startswith("…"):
            continue  # 掩码回显原样提交:保留服务端真值(审查 T-02)
        if k in LIMIT_KEYS:
            try:
                if int(text) <= 0:
                    raise ValueError
            except ValueError:
                raise HTTPException(422, f"{k} 必须为正整数") from None
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (k, text),
        )
    conn.commit()
    return {"ok": True}
