# 纯净审计 round3 修复脚本(逐条 assert):完成后删除
import io
import re

def apply(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, f'MISS {path}: {old[:60]!r}'
        s = s.replace(old, new)
    io.open(path, 'w', encoding='utf-8', newline='\n').write(s)
    print('ok', path)

# ---- 稳定性必修 1:clone 移入 to_thread(事件循环不被 clone/sleep 阻塞)+ timeout ----
apply('server/app/agents/runner.py', [
    ('''    clones_dir = clones_dir or config.data_dir() / "clones"  # 落点随数据目录
    dest = clones_dir / repo_full_name.replace("/", "__")
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, config.CLONE_ATTEMPTS + 1):
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, str(dest)],
                    check=True, capture_output=True, text=True,
                )
                break''',
     '''    clones_dir = clones_dir or config.data_dir() / "clones"  # 落点随数据目录
    dest = clones_dir / repo_full_name.replace("/", "__")
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, config.CLONE_ATTEMPTS + 1):
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", clone_url, str(dest)],
                    check=True, capture_output=True, text=True, timeout=config.CLONE_TIMEOUT_SEC,
                )
                break'''),
    ('''    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return dest, sha''',
     '''    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    return dest, sha'''),
    ('''    model = _build_model(settings)
    clone_root, sha = prepare_clone(repo["full_name"], f"https://github.com/{repo['full_name']}.git", clones_dir)''',
     '''    model = _build_model(settings)
    # 克隆(含重试退避)在工作线程执行,不阻塞本协程循环的终止 watcher
    clone_root, sha = await asyncio.to_thread(
        prepare_clone, repo["full_name"], f"https://github.com/{repo['full_name']}.git", clones_dir
    )'''),
])

# ---- 稳定性必修 2:锁定分类防影子覆盖 ----
apply('server/app/agents/runner.py', [
    ('''def upsert_classification(conn, repo_id: int, type_: str, reason: str, confidence: str, source: str) -> None:
    conn.execute("DELETE FROM classifications WHERE repo_id=? AND locked=0", (repo_id,))''',
     '''def upsert_classification(conn, repo_id: int, type_: str, reason: str, confidence: str, source: str) -> None:
    locked = conn.execute(
        "SELECT 1 FROM classifications WHERE repo_id=? AND locked=1", (repo_id,)
    ).fetchone()
    if locked and source != "manual_lock":
        raise RuntimeError("分类已人工锁定,拒绝覆盖")  # 堵 manual_scope/深读对锁定分类的影子覆盖(REQ-CLS-003)
    conn.execute("DELETE FROM classifications WHERE repo_id=? AND locked=0", (repo_id,))'''),
    ('''def set_auto_tags(conn, repo_id: int, tags: list[str]) -> None:
    """AI 分类附带的自动标签:独立 auto_tags 表,不触碰人工 tags(REQ-CLS-005);每次分析整表替换。"""
    names = [t.strip() for t in tags if t.strip()][:4]
    conn.execute("DELETE FROM auto_tags WHERE repo_id=?", (repo_id,))
    for name in names:
        conn.execute("INSERT OR IGNORE INTO auto_tags(repo_id, name) VALUES (?,?)", (repo_id, name))
    conn.commit()''',
     '''def set_auto_tags(conn, repo_id: int, tags: list[str]) -> None:
    """AI 分类附带的自动标签:独立 auto_tags 表,不触碰人工 tags(REQ-CLS-005);每次分析整表替换。不提交,与分类同事务。"""
    names = [t.strip() for t in tags if t.strip()][:config.AUTO_TAG_MAX]
    conn.execute("DELETE FROM auto_tags WHERE repo_id=?", (repo_id,))
    for name in names:
        conn.execute("INSERT OR IGNORE INTO auto_tags(repo_id, name) VALUES (?,?)", (repo_id, name))'''),
    ('''        upsert_classification(conn, repo["id"], c.output.type, c.output.reason, c.output.confidence, "auto")
        set_auto_tags(conn, repo["id"], c.output.tags)
        cls_row = current_classification(conn, repo["id"])''',
     '''        upsert_classification(conn, repo["id"], c.output.type, c.output.reason, c.output.confidence, "auto")
        set_auto_tags(conn, repo["id"], c.output.tags)
        conn.commit()  # 分类+自动标签同事务,防半态
        indexer.index_repo(conn, repo["id"])  # 自动标签入检索域(REQ-SRCH-001)
        conn.commit()
        cls_row = current_classification(conn, repo["id"])'''),
])
apply('server/app/api/routes.py', [
    ('''    if conn.execute("SELECT 1 FROM repos WHERE id=?", (repo_id,)).fetchone() is None:
        raise HTTPException(404, "仓库不存在")
    runner.upsert_classification(conn, repo_id, body["type"], body.get("reason", "人工选择范围"), body.get("confidence", "高"), "manual_scope")''',
     '''    if conn.execute("SELECT 1 FROM repos WHERE id=?", (repo_id,)).fetchone() is None:
        raise HTTPException(404, "仓库不存在")
    try:
        runner.upsert_classification(conn, repo_id, body["type"], body.get("reason", "人工选择范围"), body.get("confidence", "高"), "manual_scope")
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from None'''),
])

# ---- 稳定性必修 3:uvicorn.access 降噪 ----
apply('server/app/main.py', [
    ('''    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True''',
     '''    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    access = logging.getLogger("uvicorn.access")  # 访问日志量大,降噪保护轮转文件
    access.handlers.clear()
    access.setLevel(logging.WARNING)'''),
])

# ---- 检索/配置一致性 ----
apply('server/app/api/routes.py', [
    ('''        where += " AND (r.full_name LIKE ? OR r.description LIKE ? OR r.id IN (SELECT repo_id FROM tags WHERE name LIKE ?))"''',
     '''        where += " AND (r.full_name LIKE ? OR r.description LIKE ? OR r.id IN (SELECT repo_id FROM tags WHERE name LIKE ? UNION SELECT repo_id FROM auto_tags WHERE name LIKE ?))"''',
     ),
    ('''        args += [f"%{q}%", f"%{q}%", f"%{q}%"]''',
     '''        args += [f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"]'''),
])
apply('server/app/config.py', [
    ('CLASSIFIER_REQUEST_LIMIT = 3',
     'CLASSIFIER_REQUEST_LIMIT = 3\nAUTO_TAG_MAX = 4               # AI 分类自动标签上限\nCLONE_TIMEOUT_SEC = 600        # 单次 git clone 超时'),
])
apply('server/app/search/indexer.py', [
    ('''    tags = " ".join(
        r["name"]
        for r in conn.execute(
            "SELECT name FROM tags WHERE repo_id=? UNION ALL SELECT name FROM auto_tags WHERE repo_id=?", (repo_id, repo_id)
        )
    )''',
     '''    tags = " ".join(
        r["name"]
        for r in conn.execute(
            "SELECT name FROM tags WHERE repo_id=? UNION SELECT name FROM auto_tags WHERE repo_id=?", (repo_id, repo_id)
        )
    )'''),
])

# ---- 前端:强对比生效、.bak ----
apply('web/src/composables/useReaderSettings.js', [
    ("    root.style.setProperty('--sd-contrast', settings.contrast ? '1' : '0')",
     "    root.dataset.contrast = settings.contrast ? '1' : '0'  // 匹配 tokens 的 [data-contrast] 选择器"),
])
apply('web/src/styles/tokens.css', [
    ('/* 排版(UX-09/UX-10 修订):三档行宽 68/80/96,默认标准 80ch;间距 8 基数(UX-07) */',
     '/* 排版(UX-09/UX-10):三档行宽 72/84/100,默认标准 84ch;间距 8 基数(UX-07) */'),
    ('.search-pop {\n  position: fixed; top: 68px; left: 50%; transform: translateX(-50%);\n  width: min(680px, 92vw); background: var(--sd-elevated);\n  border: 1px solid var(--sd-border-strong); border-radius: 8px; padding: 10px; z-index: 25;\n  box-shadow: 0 12px 40px #0006;\n}'),
])
print('batch-a done')
PYEOF_MARKER = None
