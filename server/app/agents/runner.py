# Agent 运行器:克隆准备、classifier/analyzer 构建与执行、产物落库(ADR-0005;队列 executor 契约=S4)
import asyncio
import json
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from app.agents import prompts, tools, websearch
from app.render import pipeline
from app.search import indexer
from app.tasks.queue import TaskLimited

CLONES_DIR = Path("data/clones")


# ---------- 结构化产出 ----------

class ClassificationResult(BaseModel):
    type: str = Field(description="七类主类型之一")
    reason: str
    confidence: str = Field(description="高/中/低")


class EvidenceRef(BaseModel):
    kind: str = Field(description="source/author/infer/external/unknown 之一")
    ref: str = Field(description="路径:行号 或 url")


class KnowledgePoint(BaseModel):
    statement: str = Field(description="一句话结论,中文")
    evidence: list[EvidenceRef]


class Section(BaseModel):
    title: str
    body: str = Field(description="Markdown 正文,含证据块语法")


class ReportDraft(BaseModel):
    sections: list[Section] = Field(min_length=1)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)
    classification_correction: ClassificationResult | None = None


# ---------- 克隆与凭据 ----------

def prepare_clone(repo_full_name: str, clone_url: str, clones_dir: Path = CLONES_DIR) -> tuple[Path, str]:
    """浅克隆默认分支,返回 (克隆目录, head_commit);已存在则复用。commit_anchor=分析时快照(REQ-RPT-002)。"""
    dest = clones_dir / repo_full_name.replace("/", "__")
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(dest)],
            check=True, capture_output=True, text=True,
        )
    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return dest, sha


def _build_model(settings: dict):
    """按设置构建模型:ai_base_url 存在→OpenAI 兼容端点(自定义网关);否则按前缀走官方默认。"""
    model = settings.get("ai_model", "")
    api_key = settings.get("ai_api_key", "")
    base_url = settings.get("ai_base_url", "")
    if not model:
        raise RuntimeError("未配置 ai_model(系统设置)")
    if base_url:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        return OpenAIChatModel(model, provider=OpenAIProvider(base_url=base_url, api_key=api_key))
    import os

    if model.startswith("openai:"):
        os.environ["OPENAI_API_KEY"] = api_key
    elif model.startswith("anthropic:"):
        os.environ["ANTHROPIC_API_KEY"] = api_key
    else:
        raise ValueError(f"不支持的模型前缀: {model}")
    return model


# ---------- 分类与报告落库 ----------

def upsert_classification(conn, repo_id: int, type_: str, reason: str, confidence: str, source: str) -> None:
    conn.execute("DELETE FROM classifications WHERE repo_id=? AND locked=0", (repo_id,))
    conn.execute(
        "INSERT INTO classifications(repo_id, type, reason, confidence, source) VALUES (?,?,?,?,?)",
        (repo_id, type_, reason, confidence, source),
    )
    conn.commit()


def current_classification(conn, repo_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM classifications WHERE repo_id=? ORDER BY id DESC LIMIT 1", (repo_id,)
    ).fetchone()
    return dict(row) if row else None


def persist_report(conn, repo_id: int, task_id: int, commit_anchor: str, draft: ReportDraft) -> int:
    """报告落库单事务:版本+章节+FTS+知识点;分类修正遇锁定即弃(REQ-CLS-003)。返回 version_id。"""
    version_no = (
        conn.execute("SELECT COALESCE(MAX(version_no),0)+1 AS n FROM report_versions WHERE repo_id=?", (repo_id,)).fetchone()["n"]
    )
    md = "\n\n".join(f"## {s.title}\n\n{s.body}" for s in draft.sections)
    html, sections, _plain = pipeline.render(md)
    meta = {"commit_anchor": commit_anchor}
    cur = conn.execute(
        "INSERT INTO report_versions(repo_id, version_no, task_id, commit_anchor, markdown, html, sections_json, meta_json)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (repo_id, version_no, task_id, commit_anchor, md, html, json.dumps(sections, ensure_ascii=False), json.dumps(meta, ensure_ascii=False)),
    )
    version_id = cur.lastrowid
    for s in sections:
        scur = conn.execute(
            "INSERT INTO report_sections(report_version_id, seq, title, path_chain, text_content)"
            " VALUES (?,?,?,?,?)",
            (version_id, s["seq"], s["title"], s["path_chain"], s["text"]),
        )
        indexer.index_section(conn, scur.lastrowid, s["title"], s["text"])
    for kp in draft.knowledge_points:
        kcur = conn.execute(
            "INSERT INTO knowledge_points(repo_id, report_version_id, statement, evidence_json) VALUES (?,?,?,?)",
            (repo_id, version_id, kp.statement, json.dumps([e.model_dump() for e in kp.evidence], ensure_ascii=False)),
        )
        indexer.index_knowledge(conn, kcur.lastrowid)
    corr = draft.classification_correction
    if corr is not None:
        locked = current_classification(conn, repo_id)
        if not (locked and locked["locked"]):
            old = locked["type"] if locked else None
            if corr.type != old:
                upsert_classification(conn, repo_id, corr.type, corr.reason, corr.confidence, "deep")
                conn.execute(
                    "INSERT INTO classification_history(repo_id, old_type, new_type, reason) VALUES (?,?,?,?)",
                    (repo_id, old, corr.type, corr.reason),
                )
    conn.commit()
    return version_id


# ---------- 任务执行(队列 executor) ----------

async def run_task(conn, task, repo, clones_dir: Path = CLONES_DIR) -> tuple[str, int]:
    """队列 executor 契约:成功返回 ('ok', version_id);触达限额 raise TaskLimited(REQ-TASK-003)。"""
    settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    model = _build_model(settings)
    clone_root, sha = prepare_clone(repo["full_name"], f"https://github.com/{repo['full_name']}.git", clones_dir)
    deps = tools.AgentDeps(
        clone_root=clone_root,
        repo_name=repo["full_name"],
        github_token=settings.get("github_token"),
        search_chain=websearch.build_chain(settings),
    )

    cls_row = current_classification(conn, repo["id"])
    if cls_row is None:
        classifier = Agent(
            model, output_type=ClassificationResult, instructions=prompts.CLASSIFIER_INSTRUCTIONS,
        )
        readme_path = clone_root / "README.md"
        readme = f"README 摘要: {readme_path.read_text(encoding='utf-8', errors='replace')[:4000]}" if readme_path.exists() else "README 摘要: (无)"
        tree = "\n".join(f"{'d ' if p.is_dir() else 'f '}{p.name}" for p in sorted(clone_root.iterdir(), key=lambda x: (x.is_file(), x.name)))
        c = await classifier.run(f"{readme}\n\n文件树:\n{tree}")
        upsert_classification(conn, repo["id"], c.output.type, c.output.reason, c.output.confidence, "auto")
        cls_row = current_classification(conn, repo["id"])
    conn.execute("UPDATE repos SET status='已分类', updated_at=datetime('now') WHERE id=?", (repo["id"],))
    conn.commit()

    analyzer = Agent(
        model, output_type=ReportDraft, instructions=prompts.ANALYZER_INSTRUCTIONS,
        tools=[tools.read_file, tools.search_code, tools.list_dir, tools.fetch_github, tools.web_search, tools.web_fetch],
        deps_type=tools.AgentDeps,
    )
    focus = prompts.TYPE_FOCUS.get(cls_row["type"], prompts.TYPE_FOCUS["混合/未识别"])
    prompt = (
        f"仓库: {repo['full_name']}\n描述: {repo['description'] or '(无)'}\n"
        f"主类型: {cls_row['type']}(置信 {cls_row['confidence']};分类理由: {cls_row['reason']})\n"
        f"本类型报告重点: {focus}\n克隆目录即工具作用域根。产出完整中文报告。"
    )
    try:
        async with asyncio.timeout(task["time_limit_sec"]):
            result = await analyzer.run(
                prompt, deps=deps, usage_limits=UsageLimits(request_limit=task["turn_limit"]),
            )
    except (UsageLimitExceeded, TimeoutError) as e:
        raise TaskLimited(partial=False, reason=f"{'轮次上限' if isinstance(e, UsageLimitExceeded) else '任务超时'}") from e
    version_id = persist_report(conn, repo["id"], task["id"], sha, result.output)
    conn.execute("UPDATE repos SET status='可阅读', updated_at=datetime('now') WHERE id=?", (repo["id"],))
    conn.commit()
    return "ok", version_id
