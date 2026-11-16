# 分析 agent 测试:工具集(真实文件系统)、克隆(真实 git)、落库(真实 DB)
# LLM 端到端为真实调用:仅当显式设 STARDISSECT_IT_LLM=1 且有密钥时运行,否则跳过
import os
import subprocess

import pytest

from app.agents import prompts, runner, tools
from app.agents.runner import ClassificationResult, KnowledgePoint, ReportDraft, Section
from app.db import connect, init_db
from app.search import indexer


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "app.db"
    init_db(p)
    return connect(p)


@pytest.fixture()
def repo_dir(tmp_path):
    # 真实 git 仓库:本地 init + 提交,供 prepare_clone 走 file:// 真实克隆
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "README.md").write_text("# demo\n\n一个示例仓库", encoding="utf-8")
    (src / "pkg" / "core.py").write_text("def run():\n    return 42\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    subprocess.run(["git", "-C", str(src), "add", "."], check=True)
    subprocess.run(["git", "-C", str(src), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    return src


def test_prepare_clone_real_git(tmp_path, repo_dir):
    dest, sha = runner.prepare_clone("o/r", f"file://{repo_dir}", clones_dir=tmp_path / "clones")
    assert (dest / "pkg" / "core.py").exists()
    assert len(sha) == 40
    # 幂等:已存在则复用
    dest2, sha2 = runner.prepare_clone("o/r", f"file://{repo_dir}", clones_dir=tmp_path / "clones")
    assert sha2 == sha


@pytest.fixture()
def deps(tmp_path, repo_dir):
    dest, _ = runner.prepare_clone("o/r", f"file://{repo_dir}", clones_dir=tmp_path / "clones")
    return tools.AgentDeps(clone_root=dest, repo_name="o/r")


class _Ctx:
    def __init__(self, deps):
        self.deps = deps


async def test_read_file_line_numbers(deps):
    out = await tools.read_file(_Ctx(deps), "pkg/core.py")
    assert "1: def run():" in out and "2:     return 42" in out


async def test_read_file_rejects_escape(deps):
    from pathlib import Path

    deps.clone_root = Path(deps.clone_root)
    with pytest.raises(ValueError, match="越界"):
        await tools.read_file(_Ctx(deps), "../../etc/passwd")


async def test_search_code_hits_with_lines(deps):
    out = await tools.search_code(_Ctx(deps), "return 42")
    assert "pkg/core.py:2:" in out


async def test_list_dir(deps):
    out = await tools.list_dir(_Ctx(deps), ".")
    assert "d pkg" in out and "f README.md" in out


def test_persist_report_replaces_old_version(db):
    # 每仓库仅保留最新一份报告(DEC-06 修订):新版本替换旧版本,分析序号延续
    db.execute("INSERT INTO repos(id, full_name, status) VALUES (1, 'o/r', '分析中')")
    db.execute("INSERT INTO classifications(repo_id, type, reason, confidence, source) VALUES (1, '框架/库/SDK', '初判', '中', 'auto')")
    db.commit()
    draft = ReportDraft(
        sections=[
            Section(title="定位与概览", body="这是 **概览**。\n\n> [source] pkg/core.py:1-2"),
            Section(title="可迁移经验", body="结论:函数即接口。"),
        ],
        knowledge_points=[KnowledgePoint(statement="run() 返回常量 42", evidence=[])],
        classification_correction=ClassificationResult(type="应用/平台/服务", reason="深读判定", confidence="高"),
    )
    v1 = runner.persist_report(db, 1, task_id=None, commit_anchor="a" * 40, draft=draft)
    assert v1 == 1
    v2 = runner.persist_report(db, 1, task_id=None, commit_anchor="a" * 40, draft=draft)
    assert v2 == 2  # 序号=累计分析次数,替换后仍延续
    rows = db.execute("SELECT id, version_no FROM report_versions").fetchall()
    assert len(rows) == 1 and rows[0]["id"] == v2 and rows[0]["version_no"] == 2
    # 旧版本连带物清除,最新版本完整
    assert db.execute("SELECT COUNT(*) c FROM report_sections WHERE report_version_id=1").fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) c FROM knowledge_points WHERE report_version_id=1").fetchone()["c"] == 0
    assert db.execute("SELECT COUNT(*) c FROM knowledge_fts").fetchone()["c"] == 1
    # 深读修正留痕(REQ-CLS-004)
    hist = db.execute("SELECT old_type, new_type FROM classification_history").fetchone()
    assert (hist["old_type"], hist["new_type"]) == ("框架/库/SDK", "应用/平台/服务")
    # FTS 可检索(知识点 + 章节,均来自最新版)
    indexer.index_repo(db, 1)
    db.commit()
    kinds = {r["kind"] for r in indexer.search(db, "概览")}
    assert "report" in kinds
    kinds2 = {r["kind"] for r in indexer.search(db, "常量")}
    assert "knowledge" in kinds2


def test_persist_locked_classification_not_corrected(db):
    db.execute("INSERT INTO repos(id, full_name, status) VALUES (1, 'o/r', '分析中')")
    db.execute("INSERT INTO classifications(repo_id, type, reason, confidence, source, locked) VALUES (1, '框架/库/SDK', '人工', '高', 'manual_lock', 1)")
    db.commit()
    draft = ReportDraft(
        sections=[Section(title="定位", body="内容")],
        classification_correction=ClassificationResult(type="应用/平台/服务", reason="深读判定", confidence="高"),
    )
    runner.persist_report(db, 1, task_id=None, commit_anchor="a" * 40, draft=draft)
    # 锁定不被覆盖,无修正留痕(REQ-CLS-003)
    assert db.execute("SELECT type FROM classifications").fetchone()["type"] == "框架/库/SDK"
    assert db.execute("SELECT COUNT(*) c FROM classification_history").fetchone()["c"] == 0


def test_structure_check_does_not_require_a_diagram_quota():
    titles = ["定位：入口与边界", "系统设计：模块关系", "流程：请求如何执行", "取舍：数据存储", "经验：扩展方式"]
    sections = [{"title": title, "level": 2} for title in titles]

    result = runner._structure_check("\n\n".join(f"## {title}" for title in titles), sections)

    assert result == {
        "mermaid_blocks": 0,
        "heading_counts": {"h2": 5, "h3": 0},
        "missing_base_sections": [],
        "issues": [],
    }


def test_structure_check_records_nested_heading_levels():
    sections = [{"title": "系统设计", "level": 2}, {"title": "写入路径", "level": 3}]

    result = runner._structure_check("## 系统设计\n\n### 写入路径", sections)

    assert result["heading_counts"] == {"h2": 1, "h3": 1}


def test_structure_check_still_reports_missing_base_topics():
    result = runner._structure_check("## 定位概览", [{"title": "定位概览"}])

    assert result["missing_base_sections"] == ["系统设计/架构", "流程/精读", "取舍/方案", "可迁移/经验"]
    assert result["issues"] == [f"缺基础主题: {topic}" for topic in result["missing_base_sections"]]


def test_analyzer_prompt_uses_natural_style_rules_without_fixed_quotas():
    assert "不要使用“术语(一句话:...)”这类固定格式" in prompts.ANALYZER_INSTRUCTIONS
    assert "不设数量指标" in prompts.ANALYZER_INSTRUCTIONS
    assert "每段不超过 4 句" not in prompts.ANALYZER_INSTRUCTIONS
    assert "全文不少于 3 张图" not in prompts.ANALYZER_INSTRUCTIONS
    assert "每个标题须保留对应识别词" in prompts.ANALYZER_INSTRUCTIONS
    assert "用 `###` 拆出有意义的子节" in prompts.ANALYZER_INSTRUCTIONS
    assert "多个未解释的名称" in prompts.ANALYZER_INSTRUCTIONS


@pytest.mark.skipif(
    not (os.environ.get("STARDISSECT_IT_LLM") == "1" and (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))),
    reason="LLM 端到端为真实调用:需 STARDISSECT_IT_LLM=1 与密钥(CLAUDE.md:无 mock)",
)
async def test_run_task_end_to_end_with_real_llm(tmp_path):
    # 真实 LLM 全链路:克隆→分类→深读→落库→检索;需显式开启
    import asyncio

    from app.db import init_db
    from app.tasks import queue

    db_path = tmp_path / "app.db"
    init_db(db_path)
    conn = connect(db_path)
    conn.execute(
        "INSERT INTO repos(id, github_id, full_name, status, default_branch) VALUES (1, 1, 'pallets/click', '已分类')"
    )
    conn.execute(
        "INSERT INTO settings(key, value) VALUES ('ai_model', ?)",
        (os.environ.get("STARDISSECT_IT_MODEL", "anthropic:claude-haiku-4-5-20251001"),),
    )
    conn.commit()
    conn.execute("INSERT INTO tasks(repo_id, kind, status, priority, turn_limit, time_limit_sec) VALUES (1, 'analyze', '排队', 0, 30, 900)")
    conn.commit()
    task = conn.execute("SELECT * FROM tasks").fetchone()
    repo = conn.execute("SELECT * FROM repos").fetchone()
    status, version_id = await runner.run_task(conn, task, repo, clones_dir=tmp_path / "clones")
    assert status == "ok" and version_id == 1
    assert conn.execute("SELECT COUNT(*) c FROM report_sections").fetchone()["c"] > 0


def test_prepare_clone_failure_carries_git_stderr(tmp_path):
    # 克隆失败时 fail_reason 携带 git stderr 真因,而非裸退出码
    import pytest as _pytest
    from app.agents import runner as _runner

    with _pytest.raises(RuntimeError, match="git clone 失败"):
        _runner.prepare_clone("o/none", "file:///nonexistent-repo-path", clones_dir=tmp_path / "clones")
