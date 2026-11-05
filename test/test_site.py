# 报告阅读站测试(server/app/site.py):真 SQLite + 真导出目录,不碰仓库的 reports-site/
# 重建的 npm 本体不在职责里:守卫用环境缝关停,触发与否观察 dirty/锁。
import pytest

from app import config, site
from app.db import connect

from test_api import client  # noqa: F401  —— 复用真实 app + tmp 数据目录的装配

ANCHOR = "a" * 40


@pytest.fixture()
def site_dir(tmp_path, monkeypatch):
    """把 SITE_DIR 指到临时目录:导出与重建都不碰仓库里的 reports-site/。"""
    target = tmp_path / "reports-site"
    target.mkdir()
    monkeypatch.setattr(site, "SITE_DIR", target)
    return target


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "db_path", lambda: tmp_path / "app.db")
    from app.db import init_db

    init_db(tmp_path / "app.db")
    conn = connect(tmp_path / "app.db")
    conn.execute(
        "INSERT INTO repos(id, github_id, full_name, description, status) VALUES (1, 11, 'o/demo', '演示', '可阅读')"
    )
    conn.execute(
        "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, markdown, html, sections_json, meta_json, created_at)"
        " VALUES (10, 1, 2, ?, '# 标题\n\n> [source] core.py:1', '', '[]', '{}', '2026-01-02 03:04:05')",
        (ANCHOR,),
    )
    conn.commit()
    yield conn
    conn.close()


def test_export_site_writes_slug_dirs_with_frontmatter(db, site_dir):
    site.export_site(db)

    page = (site_dir / "src" / "o__demo" / "10" / "index.md").read_text(encoding="utf-8")
    # frontmatter 六字段:工具条与源码链接的消费契约
    assert 'title: "o/demo v2"' in page
    assert 'repo: "o/demo"' in page
    assert 'version: 2' in page
    assert f'commit: "{"a" * 40}"' in page
    assert 'generated_at: "2026-01-02 03:04:05"' in page
    assert 'vid: 10' in page
    # 正文经 _normalize_fences 预整形,证据块语法原样(渲染加工归站点插件)
    assert "> [source] core.py:1" in page


def test_home_lists_each_report_on_its_own_line(db, site_dir):
    db.execute(
        "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, markdown, html, sections_json, meta_json, created_at)"
        " VALUES (12, 1, 4, ?, '# 另一份', '', '[]', '{}', '2026-01-03 03:04:05')",
        (ANCHOR,),
    )
    db.commit()

    site.export_site(db)

    home = (site_dir / "src" / "index.md").read_text(encoding="utf-8")
    assert "- [o/demo v4](/o__demo/12/)\n- [o/demo v2](/o__demo/10/)\n" in home


def test_export_site_rebuilds_the_whole_tree(db, site_dir):
    site.export_site(db)
    # 追加一份再删一份:整树重摆后,新份在、旧份无、首页不再提
    db.execute(
        "INSERT INTO report_versions(id, repo_id, version_no, commit_anchor, markdown, html, sections_json, meta_json, created_at)"
        " VALUES (11, 1, 3, ?, '# 新报告', '', '[]', '{}', '2026-02-01 00:00:00')",
        ("b" * 40,),
    )
    db.execute("DELETE FROM report_versions WHERE id=10")
    db.commit()

    site.export_site(db)

    assert (site_dir / "src" / "o__demo" / "11").exists()
    assert not (site_dir / "src" / "o__demo" / "10").exists()
    assert "10" not in (site_dir / "src" / "index.md").read_text(encoding="utf-8")
    assert "(/o__demo/11/)" in (site_dir / "src" / "index.md").read_text(encoding="utf-8")


def test_export_site_hides_archived(db, site_dir):
    db.execute("UPDATE report_versions SET archived=1 WHERE id=10")
    db.commit()

    site.export_site(db)

    assert not (site_dir / "src" / "o__demo").exists()
    assert "还没有报告" in (site_dir / "src" / "index.md").read_text(encoding="utf-8")


def test_normalize_fences_repairs_glued_and_unclosed():
    # 行中粘连拆行 + 未闭合围栏在空行处闭合(与 SPA 阅读同一道入口整形)
    glued = site.pipeline._normalize_fences("前文```python x=1 ```后文")
    assert "```python\n" in glued
    unclosed = site.pipeline._normalize_fences("```python\nx=1\n\n正文跟进了")
    assert unclosed.count("```") % 2 == 0


def test_schedule_rebuild_guards_are_silent_no_ops(site_dir, monkeypatch):
    # 环境缝关停(测试全局默认)与脚手架缺失:不立 dirty、不派工人
    import os

    assert os.environ.get("STARDISSECT_SITE_REBUILD") == "0"
    site.schedule_rebuild()
    assert not site._dirty.is_set()

    monkeypatch.setenv("STARDISSECT_SITE_REBUILD", "1")
    site.schedule_rebuild()  # package.json 不在(临时 SITE_DIR 是空的)
    assert not site._dirty.is_set()

    (site_dir / "package.json").write_text("{}", encoding="utf-8")
    site.schedule_rebuild()  # node_modules 不在
    assert not site._dirty.is_set()


async def test_post_site_rebuild_is_a_scheduled_noop(client):
    # 端点排程即返回;测试环境守卫关停(STARDISSECT_SITE_REBUILD=0),不真构建
    c, _conn = client
    r = await c.post("/api/site/rebuild")
    assert r.status_code == 200
    assert r.json() == {"started": True}
