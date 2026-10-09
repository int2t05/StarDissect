# 检索:三域索引与查询(ADR-0006;范围=报告章节/知识点/仓库元信息,REQ-SRCH-001)
from app.db import connect  # noqa: F401  测试与调用方共用同一连接工厂
import re

import jieba
import nh3

_CJK = r"\u4e00-\u9fff"
# 片段来自分词文本,按 CJK 相邻去空格还原阅读形态;mark 标签位置不受影响
_STRIP = re.compile(rf"\s+(?=[{_CJK}])|(?<=[{_CJK}])\s+")


def tokenize(text: str) -> str:
    # 索引与查询共用;空格连接供 FTS5 unicode61 消费
    return " ".join(w for w in (t.strip() for t in jieba.lcut(text)) if w)


def _match_expr(query: str) -> str:
    words = tokenize(query).split()
    return " AND ".join('"%s"' % w.replace('"', '""') for w in words)


def index_section(conn, section_id: int, title: str, text_content: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO report_fts(rowid, title, text_content) VALUES (?,?,?)",
        (section_id, tokenize(title), tokenize(text_content)),
    )


def _index_external(conn, fts_table: str, content_table: str, column: str, rowid: int) -> None:
    row = conn.execute(f"SELECT {column} FROM {content_table} WHERE id=?", (rowid,)).fetchone()
    if row is None:
        return
    conn.execute(
        f"INSERT OR REPLACE INTO {fts_table}(rowid, {column}) VALUES (?,?)",
        (rowid, tokenize(row[0])),
    )


def index_knowledge(conn, knowledge_id: int) -> None:
    _index_external(conn, "knowledge_fts", "knowledge_points", "statement", knowledge_id)


def index_repo(conn, repo_id: int) -> None:
    row = conn.execute("SELECT full_name, description FROM repos WHERE id=?", (repo_id,)).fetchone()
    if row is None:
        return
    conn.execute(
        "INSERT OR REPLACE INTO repo_fts(rowid, full_name, description) VALUES (?,?,?)",
        (repo_id, tokenize(row["full_name"]), tokenize(row["description"] or "")),
    )


def _humanize(snippet: str) -> str:
    return _STRIP.sub("", snippet)


def search(conn, query: str, limit: int = 20) -> list[dict]:
    match = _match_expr(query)
    if not match:
        return []
    report_sql = """
        SELECT 'report' AS kind, r.id AS repo_id, r.full_name,
               rv.id AS version_id, rv.version_no, s.seq, s.title, s.path_chain,
               snippet(report_fts, 1, '<mark>', '</mark>', '…', 16) AS snippet
        FROM report_fts
        JOIN report_sections s ON s.id = report_fts.rowid
        JOIN report_versions rv ON rv.id = s.report_version_id
        JOIN repos r ON r.id = rv.repo_id
        WHERE report_fts MATCH ? LIMIT ?"""
    knowledge_sql = """
        SELECT 'knowledge' AS kind, r.id AS repo_id, r.full_name,
               rv.id AS version_id, rv.version_no, NULL AS seq,
               kp.statement AS title, NULL AS path_chain,
               snippet(knowledge_fts, 0, '<mark>', '</mark>', '…', 16) AS snippet
        FROM knowledge_fts
        JOIN knowledge_points kp ON kp.id = knowledge_fts.rowid
        JOIN report_versions rv ON rv.id = kp.report_version_id
        JOIN repos r ON r.id = kp.repo_id
        WHERE knowledge_fts MATCH ? LIMIT ?"""
    repo_sql = """
        SELECT 'repo' AS kind, r.id AS repo_id, r.full_name,
               NULL AS version_id, NULL AS version_no, NULL AS seq,
               NULL AS title, NULL AS path_chain,
               snippet(repo_fts, 1, '<mark>', '</mark>', '…', 16) AS snippet
        FROM repo_fts
        JOIN repos r ON r.id = repo_fts.rowid
        WHERE repo_fts MATCH ? LIMIT ?"""
    hits: list[dict] = []
    for sql in (report_sql, knowledge_sql, repo_sql):
        for row in conn.execute(sql, (match, limit)):
            hit = dict(row)
            # UX-41:服务端转义正文后仅保留 <mark> 白名单,防报告内容注入
            hit["snippet"] = nh3.clean(_humanize(hit["snippet"]), tags={"mark"})
            hits.append(hit)
    return hits
