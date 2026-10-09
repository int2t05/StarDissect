# 网络搜索工具链(参考 Cognik:server/internal/infra/adapter/search_client.go 降级链模式)
# 顺序降级 Tavily→Exa→DuckDuckGo,首个成功即返回;片段是线索不是证据,引用前须 web_fetch 核实
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx


@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


class TavilyClient:
    name = "tavily"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[WebSearchResult]:
        r = await client.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": query, "max_results": max_results},
        )
        r.raise_for_status()
        return [WebSearchResult(x["title"], x["url"], x.get("content", "")) for x in r.json().get("results", [])]


class ExaClient:
    name = "exa"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[WebSearchResult]:
        r = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": self.api_key},
            json={"query": query, "type": "auto", "numResults": max_results, "contents": {"highlights": True}},
        )
        r.raise_for_status()
        return [
            WebSearchResult(x["title"], x["url"], (x.get("highlights") or [""])[0])
            for x in r.json().get("results", [])
        ]


class DuckDuckGoClient:
    name = "duckduckgo"

    async def search(self, client: httpx.AsyncClient, query: str, max_results: int) -> list[WebSearchResult]:
        # HTML 端点无 key 兜底;重定向链接形如 /l/?uddg=<编码URL>
        r = await client.get(
            f"https://html.duckduckgo.com/html/?q={quote(query)}",
            headers={"User-Agent": "Mozilla/5.0 (compatible; StarDissect/1.0)"},
        )
        r.raise_for_status()
        results: list[WebSearchResult] = []
        for m in re.finditer(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r.text):
            href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
            parsed = urlparse(href)
            if parsed.path == "/l/":
                href = unquote(parse_qs(parsed.query).get("uddg", [href])[0])
            if href.startswith("http"):
                results.append(WebSearchResult(title.strip(), href))
            if len(results) >= max_results:
                break
        return results


class SearchChain:
    def __init__(self, backends: list):
        self.backends = backends

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        errors: list[str] = []
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for backend in self.backends:
                try:
                    results = await backend.search(client, query, max_results)
                    if results:
                        return results
                except Exception as e:  # noqa: BLE001 —— 降级到下一后端
                    errors.append(f"{backend.name}: {type(e).__name__}")
        if errors and not self.backends:
            raise RuntimeError("未配置任何搜索后端")
        return []


def build_chain(settings: dict) -> SearchChain:
    """按可用密钥组装降级链;.env/设置表注入 tavily_api_key/exa_api_key。"""
    backends = []
    if settings.get("tavily_api_key"):
        backends.append(TavilyClient(settings["tavily_api_key"]))
    if settings.get("exa_api_key"):
        backends.append(ExaClient(settings["exa_api_key"]))
    backends.append(DuckDuckGoClient())
    return SearchChain(backends)


def format_results(results: list[WebSearchResult]) -> str:
    if not results:
        return "无搜索结果"
    return "\n".join(
        f"[{i}] {r.title}\n    {r.url}" + (f"\n    {r.snippet[:200]}" if r.snippet else "")
        for i, r in enumerate(results, 1)
    )
