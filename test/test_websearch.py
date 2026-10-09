# 搜索工具链测试(参考 Cognik 降级链模式);真实网络调用走门控
import os

import pytest

from app.agents import websearch


def test_format_results_numbered():
    out = websearch.format_results([
        websearch.WebSearchResult("标题甲", "https://a.example"),
        websearch.WebSearchResult("标题乙", "https://b.example", "片段"),
    ])
    assert out.startswith("[1] 标题甲") and "https://b.example" in out and "片段" in out
    assert websearch.format_results([]) == "无搜索结果"


def test_chain_empty_backends_returns_empty():
    chain = websearch.SearchChain([])
    import asyncio

    assert asyncio.run(chain.search("q")) == []


def test_build_chain_order_from_settings():
    chain = websearch.build_chain({"tavily_api_key": "t", "exa_api_key": "e"})
    assert [b.name for b in chain.backends] == ["tavily", "exa", "duckduckgo"]
    assert [b.name for b in websearch.build_chain({}).backends] == ["duckduckgo"]


@pytest.mark.skipif(
    not os.environ.get("TAVILY_API_KEY"),
    reason="真实搜索调用:需 TAVILY_API_KEY(注入于 .env;CLAUDE.md:无 mock)",
)
async def test_tavily_real_search():
    chain = websearch.SearchChain([websearch.TavilyClient(os.environ["TAVILY_API_KEY"])])
    results = await chain.search("pydantic-ai python agent framework", 3)
    assert results and results[0].url.startswith("http")
