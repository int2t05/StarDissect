# SQLite 数据层:WAL 连接、schema 迁移(ADR-0002;DDL 契约=docs/v1.0/tech.md §2)
# 约束:report_versions 只增不覆(DEC-06);tags/knowledge_points 修订无自动写路径(REQ-CLS-005/KP-002)
import sqlite3
from pathlib import Path

# FTS5 自持文本表:索引存分词副本,snippet() 从副本取(中文预分词与 external content 的
# 偏移矛盾,修订见 ADR-0006);写入方在检索模块(ADR-0006)
SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY,
    github_id INTEGER UNIQUE,
    full_name TEXT NOT NULL,
    description TEXT,
    language TEXT,
    default_branch TEXT,
    status TEXT NOT NULL DEFAULT '已收录',   -- 仓库态:已收录/已分类/待处理/可阅读(任务态见 tasks 表)
    excluded INTEGER NOT NULL DEFAULT 0,
    unstarred INTEGER NOT NULL DEFAULT 0,
    starred_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    type TEXT NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('高','中','低')),
    source TEXT NOT NULL CHECK (source IN ('auto','deep','manual_lock','manual_scope')),
    locked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classification_history (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    old_type TEXT,
    new_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS auto_tags (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repo_id, name)
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repo_id, name)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    kind TEXT NOT NULL CHECK (kind IN ('analyze','reanalyze')),
    status TEXT NOT NULL CHECK (status IN ('排队','进行','完成','失败','中断')),
    priority INTEGER NOT NULL DEFAULT 100,
    turn_limit INTEGER NOT NULL,
    time_limit_sec INTEGER NOT NULL,
    auto_retries INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    fail_reason TEXT
);

CREATE TABLE IF NOT EXISTS report_versions (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    version_no INTEGER NOT NULL,
    task_id INTEGER REFERENCES tasks(id),
    commit_anchor TEXT NOT NULL,
    markdown TEXT NOT NULL DEFAULT '',
    html TEXT NOT NULL,
    sections_json TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    read INTEGER NOT NULL DEFAULT 0,
    favorited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repo_id, version_no)
);

CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY,
    repo_id INTEGER NOT NULL REFERENCES repos(id),
    report_version_id INTEGER NOT NULL REFERENCES report_versions(id),
    statement TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    human_edited INTEGER NOT NULL DEFAULT 0,
    revision_note TEXT,
    deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reading_progress (
    report_version_id INTEGER PRIMARY KEY REFERENCES report_versions(id),
    anchor TEXT,
    top_percent REAL NOT NULL DEFAULT 0,
    bottom_percent REAL NOT NULL DEFAULT 0,
    highest_anchor TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    added INTEGER NOT NULL DEFAULT 0,
    removed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_sections (
    id INTEGER PRIMARY KEY,
    report_version_id INTEGER NOT NULL REFERENCES report_versions(id),
    seq INTEGER NOT NULL,
    title TEXT NOT NULL,
    path_chain TEXT NOT NULL,
    text_content TEXT NOT NULL DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS report_fts USING fts5(
    title, text_content
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    statement
);

CREATE VIRTUAL TABLE IF NOT EXISTS repo_fts USING fts5(
    full_name, description
);
"""

# 版本 → 该版本的增量语句(列变更等 SCHEMA 重放覆盖不到的)
MIGRATIONS = {
    3: ["ALTER TABLE tasks ADD COLUMN auto_retries INTEGER NOT NULL DEFAULT 0"],
}

ALL_TABLES = {
    "repos", "classifications", "classification_history", "auto_tags", "tags", "tasks",
    "report_versions", "knowledge_points", "reading_progress", "sync_runs",
    "settings", "report_sections", "report_fts", "knowledge_fts", "repo_fts",
}


SCHEMA_VERSION = 3  # 结构变更:更新 SCHEMA 并递增版本;SCHEMA 全 IF NOT EXISTS 幂等重放建新表,
                    # 列变更走 MIGRATIONS 显式语句(按版本顺序执行)


def connect(db_path: Path) -> sqlite3.Connection:
    # WAL + 外键强制 + 忙等待;多连接(每请求/工作线程各一)靠 WAL 串行写
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < SCHEMA_VERSION:
            conn.executescript(SCHEMA)  # 全 IF NOT EXISTS:新库建全量,旧库幂等补齐
            for v in range(version, SCHEMA_VERSION):
                for stmt in MIGRATIONS.get(v + 1, []):
                    try:
                        conn.execute(stmt)
                    except sqlite3.OperationalError:
                        pass  # 幂等:列已存在等场景
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()
