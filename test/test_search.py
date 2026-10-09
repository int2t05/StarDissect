# 检索测试:jieba 分词、三域索引、snippet 命中(ADR-0006、REQ-SRCH-001)
from app.db import connect, init_db
from app.search import indexer


def _seed(db_path):
    init_db(db_path)
    conn = connect(db_path)
    conn.execute("INSERT INTO repos(id, github_id, full_name, description) VALUES (1, 11, 'miniflux/miniflux', '极简 订阅 阅读器 扩展 机制 示例')")
    conn.execute(
        "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, html, sections_json)"
        " VALUES (10, 1, 1, 'abc', '<p>x</p>', '[]')"
    )
    conn.execute(
        "INSERT INTO report_sections(id, report_version_id, seq, title, path_chain, text_content)"
        " VALUES (100, 10, 0, '系统 设计', '0', '')"
    )
    conn.execute(
        "INSERT INTO knowledge_points(id, repo_id, report_version_id, statement, evidence_json)"
        " VALUES (200, 1, 10, '扩展 机制 基于 中间件', '[]')"
    )
    indexer.index_section(conn, 100, "系统 设计", "扩展 机制 基于 中间件 层")
    indexer.index_knowledge(conn, 200)
    indexer.index_repo(conn, 1)
    conn.commit()
    return conn


def test_tokenize_segments_and_joins(tmp_path):
    out = indexer.tokenize("模块边界清晰且可扩展")
    assert out == "模块 边界 清晰 且 可 扩展" or out.count(" ") >= 2  # 分词非空且空格连接
    assert indexer.tokenize("") == ""


def _hit_kinds(conn, q):
    return [r["kind"] for r in indexer.search(conn, q)]


def test_search_hits_all_three_domains(tmp_path):
    conn = _seed(tmp_path / "app.db")
    kinds = _hit_kinds(conn, "扩展机制")
    assert set(kinds) == {"report", "knowledge", "repo"}
    conn.close()


def test_report_hit_carries_grouping_fields(tmp_path):
    conn = _seed(tmp_path / "app.db")
    rows = [r for r in indexer.search(conn, "扩展机制") if r["kind"] == "report"]
    r = rows[0]
    assert (r["repo_id"], r["version_no"], r["seq"], r["path_chain"]) == (1, 1, 0, "0")
    assert r["title"] == "系统 设计"
    assert "<mark>" in r["snippet"] and "扩展" in r["snippet"]
    conn.close()


def test_snippet_humanized_strips_cjk_spaces(tmp_path):
    conn = _seed(tmp_path / "app.db")
    rows = [r for r in indexer.search(conn, "扩展机制") if r["kind"] == "report"]
    # 检索列存的是分词文本,片段按 CJK 相邻去空格还原阅读形态;mark 保持
    assert "基 于" not in rows[0]["snippet"]
    assert "<mark>" in rows[0]["snippet"]
    conn.close()


def test_search_no_result_is_empty(tmp_path):
    conn = _seed(tmp_path / "app.db")
    assert indexer.search(conn, "不存在的词组xyzq") == []
    conn.close()
