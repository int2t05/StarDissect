# 存量报告修复:全部 report_versions 重渲染至当前管线
# (围栏整形/mermaid 标签引号/证据折叠与准入降级/nh3 消毒),并同步修复 markdown 源。
# 用法(仓库根):server/.venv/bin/python scripts/repair_reports.py [--dry]
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import nh3  # noqa: E402

from app.agents.runner import CLEAN_ATTRS, CLEAN_TAGS, _structure_check, _typography_check  # noqa: E402
from app import config  # noqa: E402
from app.db import connect, init_db  # noqa: E402
from app.render import pipeline  # noqa: E402
from app.search import indexer  # noqa: E402

dry = "--dry" in sys.argv
init_db(config.db_path())
conn = connect(config.db_path())

rows = conn.execute("SELECT id, markdown, meta_json FROM report_versions ORDER BY id").fetchall()
fixed_md = fixed_html = skipped = 0
for r in rows:
    md_old = r["markdown"]
    md_new = pipeline._normalize_fences(md_old)
    html, sections, plain = pipeline.render(md_new)
    html = nh3.clean(html, tags=CLEAN_TAGS, attributes=CLEAN_ATTRS, url_schemes={"http", "https", "mailto"})
    meta = json.loads(r["meta_json"] or "{}")
    meta["typography_check"] = _typography_check(plain)
    meta["structure_check"] = _structure_check(md_new, sections)
    changed = (md_new != md_old) or (html != r["html"])
    if dry:
        if changed:
            fixed_html += 1
        continue
    if md_new != md_old:
        fixed_md += 1
    fixed_html += 1
    conn.execute(
        "UPDATE report_versions SET markdown=?, html=?, sections_json=?, meta_json=? WHERE id=?",
        (md_new, html, json.dumps(sections, ensure_ascii=False), json.dumps(meta, ensure_ascii=False), r["id"]),
    )
    old_ids = [x["id"] for x in conn.execute(
        "SELECT id FROM report_sections WHERE report_version_id=?", (r["id"],))]
    for sid in old_ids:
        conn.execute("DELETE FROM report_fts WHERE rowid=?", (sid,))
    conn.execute("DELETE FROM report_sections WHERE report_version_id=?", (r["id"],))
    for s in sections:
        cur = conn.execute(
            "INSERT INTO report_sections(report_version_id, seq, title, path_chain, text_content)"
            " VALUES (?,?,?,?,?)",
            (r["id"], s["seq"], s["title"], s["path_chain"], s["text"]),
        )
        indexer.index_section(conn, cur.lastrowid, s["title"], s["text"])
    conn.commit()

print(f"共 {len(rows)} 份报告 · md 整形 {fixed_md} · 重渲染 {fixed_html} · dry={dry}")
