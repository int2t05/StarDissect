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
