# Agent 工具集:作用域限仓库克隆区与只读外部访问(契约=docs/v1.0/tech.md §4)
# 证据锚定:read_file/search_code 输出带真实行号,供 [source] 证据引用(REQ-RPT-002)
# 网络搜索纪律(线索≠证据)的唯一陈述在 tech.md §4,此处工具 docstring 仅简述并回指
import os
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic_ai import RunContext

from app import config
from app.agents import websearch

REPO_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".c", ".h", ".cpp",
    ".md", ".toml", ".yaml", ".yml", ".json", ".sh", ".sql", ".vue", ".cs", ".php", ".kt", ".swift",
}


@dataclass
class AgentDeps:
    clone_root: Path          # 克隆区根(逃逸防护边界)
    repo_name: str            # full_name,供 GitHub 只读调用
    github_token: str | None = None
    search_chain: "websearch.SearchChain | None" = None  # 网络搜索降级链(参考 Cognik 模式)


def _resolve(deps: AgentDeps, rel: str) -> Path:
    root = deps.clone_root.resolve()
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"路径越界: {rel}")
    return p


async def read_file(ctx: RunContext[AgentDeps], path: str, start: int = 1, end: int = config.MAX_FILE_LINES) -> str:
    """读克隆区文件,返回带行号文本;行区间限长防刷屏;系统路径异常如实报错不崩溃。"""
    try:
        p = _resolve(ctx.deps, path)
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"读取失败: {e}"
    start = max(1, start)
    end = min(len(lines), end, start + config.MAX_FILE_LINES - 1)
    body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
    if end < len(lines):
        body += f"\n…(共 {len(lines)} 行,已截断)"
    return body or "(空文件)"


async def search_code(ctx: RunContext[AgentDeps], pattern: str, suffix: str = "") -> str:
    """在克隆区按正则搜代码文本,返回 path:line: 内容(限 50 条)。suffix 限定文件后缀,如 .py。"""
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"正则无效: {e}"
    hits: list[str] = []
    root = ctx.deps.clone_root
    # 仓库内容不可控(Windows 非法路径/断链):遍历与读取逐项容错跳过
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "dist", "build")]
        for name in filenames:
            if suffix and not name.endswith(suffix):
                continue
            if Path(name).suffix not in REPO_SUFFIXES:
                continue
            f = Path(dirpath) / name
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        rel = f.relative_to(root).as_posix()
                        hits.append(f"{rel}:{i}: {line.strip()}")
                        if len(hits) >= config.MAX_SEARCH_HITS:
                            return "\n".join(hits) + "\n…(已达上限)"
            except OSError:
                continue
    return "\n".join(hits) if hits else "(无命中)"


async def list_dir(ctx: RunContext[AgentDeps], path: str = ".") -> str:
    """列出克隆区目录(单层),便于定位结构。"""
    try:
        p = _resolve(ctx.deps, path)
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
    except OSError as e:
        return f"读取失败: {e}"
    return "\n".join(("d " if e.is_dir() else "f ") + e.name for e in entries) or "(空目录)"


async def fetch_github(ctx: RunContext[AgentDeps], kind: str, number: int = 0) -> str:
    """GitHub 只读:kind=readme|issue|issues_list;证据归「作者说明/外部背景」。
    请求失败返回错误文本而非抛出——agent 可降级为 [unknown] 证据,循环不中断。"""
    headers = {"Accept": "application/vnd.github+json"}
    if ctx.deps.github_token:
        headers["Authorization"] = f"Bearer {ctx.deps.github_token}"
    base = f"https://api.github.com/repos/{ctx.deps.repo_name}"
    try:
        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
            if kind == "readme":
                r = await client.get(f"{base}/readme", headers={**headers, "Accept": "application/vnd.github.raw"})
                r.raise_for_status()
                return r.text[:config.MAX_WEB_CHARS]
            if kind == "issue":
                r = await client.get(f"{base}/issues/{number}")
                r.raise_for_status()
                d = r.json()
                return f"#{d['number']} {d['title']}\n{d.get('body') or ''}"[:config.MAX_WEB_CHARS]
            if kind == "issues_list":
                r = await client.get(f"{base}/issues", params={"per_page": 10, "state": "all"})
                r.raise_for_status()
                return "\n".join(f"#{d['number']} [{d['state']}] {d['title']}" for d in r.json())
    except httpx.HTTPError as e:
        return f"获取失败: {e}"
    return f"未知 kind: {kind}"


async def web_search(ctx: RunContext[AgentDeps], query: str, max_results: int = 5) -> str:
    """网络搜索(Tavily→Exa→DuckDuckGo 降级链)。
    片段是线索不是证据——引用前必须用 web_fetch 打开源页面核实,归「外部背景」证据。"""
    if ctx.deps.search_chain is None:
        return "未配置搜索后端"
    results = await ctx.deps.search_chain.search(query, max(max_results, 1))
    if not results and ctx.deps.search_chain.last_errors:
        # 全后端失败:透出错误摘要,不让 agent 误判为「无结果」
        return "搜索后端均失败:" + "; ".join(ctx.deps.search_chain.last_errors)
    return websearch.format_results(results)


async def deep_research(ctx: RunContext[AgentDeps], topic: str, max_pages: int = 3) -> str:
    """深度调研:搜索并抓取前 N 页正文蒸馏,多源合并;引用其中 URL 前仍须按证据规则标注。
    适合为「外部背景/方案取舍」收集多源材料;调用消耗计入轮次预算。"""
    if ctx.deps.search_chain is None:
        return "未配置搜索后端"
    return await websearch.deep_research(ctx.deps.search_chain, topic, max(min(max_pages, config.MAX_DEEP_PAGES), 1))


async def web_fetch(ctx: RunContext[AgentDeps], url: str) -> str:
    """抓取外部网页/文档文本;证据归「外部背景」,须记录查阅来源;失败返回错误文本。"""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text[:config.MAX_WEB_CHARS]
    except httpx.HTTPError as e:
        return f"获取失败: {e}"
