# 数据层测试:真实建库,验证表结构、WAL 与外键;无 mock
import sqlite3

import pytest

from app.db import ALL_TABLES, init_db


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "app.db"


def test_init_db_creates_all_tables(db_path):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert ALL_TABLES <= names


def test_init_db_enables_wal(db_path):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"


def test_init_db_idempotent(db_path):
    init_db(db_path)
    init_db(db_path)  # 重复迁移不报错、不破坏数据


def test_fts_external_content_wired(db_path):
    # 章节行写入后,FTS 虚表按 external content 反映同一 rowid
    # 写入路径=索引期 jieba 预分词后的空格连接(ADR-0006);unicode61 对未分词 CJK 整段成单 token
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO report_sections(id, report_version_id, seq, title, path_chain, text_content)"
        " VALUES (1, 1, 0, '系统 设计', '0/1', '模块 边界 清晰')"
    )
    conn.execute("INSERT INTO report_fts(rowid, title, text_content) VALUES (1, '系统 设计', '模块 边界 清晰')")
    hit = conn.execute("SELECT rowid FROM report_fts WHERE report_fts MATCH '模块'").fetchone()
    conn.close()
    assert hit == (1,)


def test_new_schema_carries_v5_columns(db_path):
    # v5:归档旗标与更新检测三列直达(新库 SCHEMA 建全量)
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    repos_cols = {r[1] for r in conn.execute("PRAGMA table_info(repos)")}
    rv_cols = {r[1] for r in conn.execute("PRAGMA table_info(report_versions)")}
    conn.close()
    assert {"archived", "behind_count", "behind_checked_at", "behind_anchor"} <= repos_cols
    assert "archived" in rv_cols


# v4 时点的 repos / report_versions 结构(v5 迁移模拟底座;tasks 等未涉表省略)
_V4_SCHEMA = """
CREATE TABLE repos (
    id INTEGER PRIMARY KEY, github_id INTEGER UNIQUE, full_name TEXT NOT NULL,
    description TEXT, language TEXT, default_branch TEXT,
    status TEXT NOT NULL DEFAULT '已收录',
    excluded INTEGER NOT NULL DEFAULT 0, unstarred INTEGER NOT NULL DEFAULT 0,
    starred_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE report_versions (
    id INTEGER PRIMARY KEY, repo_id INTEGER NOT NULL REFERENCES repos(id),
    version_no INTEGER NOT NULL, task_id INTEGER REFERENCES tasks(id),
    commit_anchor TEXT NOT NULL, markdown TEXT NOT NULL DEFAULT '', html TEXT NOT NULL,
    sections_json TEXT NOT NULL, meta_json TEXT NOT NULL DEFAULT '{}',
    read INTEGER NOT NULL DEFAULT 0, favorited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repo_id, version_no)
);
"""


def test_migration_v4_upgrade(db_path):
    # 旧库(v4)升级:五列补齐 + 数据迁移至当前版本,既有数据保留且默认未归档
    conn = sqlite3.connect(db_path)
    conn.executescript(_V4_SCHEMA)
    conn.execute("INSERT INTO repos(id, full_name, status) VALUES (1, 'o/old', '已分类')")
    conn.execute("PRAGMA user_version=4")
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
    repos_cols = {r[1] for r in conn.execute("PRAGMA table_info(repos)")}
    assert {"archived", "behind_count", "behind_checked_at", "behind_anchor"} <= repos_cols
    rv_cols = {r[1] for r in conn.execute("PRAGMA table_info(report_versions)")}
    assert "archived" in rv_cols
    row = conn.execute("SELECT full_name, archived, behind_count FROM repos WHERE id=1").fetchone()
    assert row[0] == "o/old" and row[1] == 0 and row[2] is None
    conn.close()


def test_migration_v6_dedupes_report_versions(db_path):
    # v6 数据迁移:存量多版本收敛为每仓库最新一份(连带章节/知识点/进度/FTS)
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO repos(id, full_name) VALUES (1, 'o/r')")
    for vid, ver in ((10, 1), (11, 2)):
        conn.execute(
            "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, html, sections_json)"
            " VALUES (?, 1, ?, 'a', 'x', '[]')", (vid, ver))
        conn.execute(
            "INSERT INTO report_sections(id, report_version_id, seq, title, path_chain, text_content)"
            " VALUES (?, ?, 0, 't', '0', 'x')", (vid * 10, vid))
        conn.execute("INSERT INTO report_fts(rowid, title, text_content) VALUES (?, 't', 'x')", (vid * 10,))
        conn.execute(
            "INSERT INTO knowledge_points(id, repo_id, report_version_id, statement, evidence_json)"
            " VALUES (?, 1, ?, 's', '[]')", (vid * 100, vid))
        conn.execute("INSERT INTO knowledge_fts(rowid, statement) VALUES (?, 's')", (vid * 100,))
    conn.execute("INSERT INTO reading_progress(report_version_id, top_percent, bottom_percent) VALUES (10, 5, 5)")
    conn.execute("PRAGMA user_version=5")
    conn.commit()
    conn.close()

    init_db(db_path)

    conn = sqlite3.connect(db_path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 6
    rows = conn.execute("SELECT id, version_no FROM report_versions").fetchall()
    assert rows == [(11, 2)]  # 仅保留最新一份,序号延续
    assert conn.execute("SELECT COUNT(*) FROM report_sections").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM report_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM reading_progress").fetchone()[0] == 0  # 旧版进度清除
    conn.close()
