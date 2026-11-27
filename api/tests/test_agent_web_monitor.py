"""Offline contracts: fixed-origin search, grounded evidence, safe recurring monitors."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_platform.web_research import (
    SearchUnavailable, normalize_query, safe_source_url, search_sources,
)
from agent_platform.monitor import (
    MonitorInput, canonical_sources, compare_sources, fingerprint, run_monitor,
)
from agent_platform.monitor_admin import authorized, validate_cron


def test_free_wikipedia_search_parses_sources_not_html():
    def wikipedia(request):
        assert request.url.host == "en.wikipedia.org"
        assert request.url.path == "/w/rest.php/v1/search/page"
        assert request.url.params["q"] == "George Washington president"
        return httpx.Response(200, json={"pages": [
            {"key": "George_Washington", "title": "George Washington",
             "excerpt": "<b>George Washington</b> was the first president."}
        ]})
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(wikipedia)) as client:
            return await search_sources("George Washington president", client=client)
    result = asyncio.run(go())
    assert result["source_scope"] == "encyclopedia-only"
    assert result["results"][0]["url"] == "https://en.wikipedia.org/wiki/George_Washington"
    assert "<b>" not in result["results"][0]["snippet"]


def test_external_search_results_reject_unsafe_source_links(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_BRAVE_SEARCH_API_KEY", "synthetic-key")
    def brave(request):
        assert request.url.host == "api.search.brave.com"
        assert request.headers["X-Subscription-Token"] == "synthetic-key"
        return httpx.Response(200, json={"web": {"results": [
            {"title": "Internal address", "url": "https://127.0.0.1/secrets",
             "description": "Not a valid external citation"},
            {"title": "Safe source", "url": "https://example.org/item",
             "description": "A <b>published</b> source"},
            {"title": "Bad port", "url": "https://example.org:abc",
             "description": "Reject malformed port"},
            {"title": "Bad scheme", "url": "http://example.org",
             "description": "Reject insecure source"},
        ]}})
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(brave)) as client:
            return await search_sources("industrial robotics", provider="brave",
                                        limit=4, client=client)
    data = asyncio.run(go())
    assert len(data["results"]) == 1
    assert data["results"][0]["url"] == "https://example.org/item"
    assert data["results"][0]["snippet"] == "A published source"
    assert not safe_source_url("https://192.168.0.1/")
    assert not safe_source_url("https://foo.internal/")
    assert not safe_source_url("https://example.org:bad/")


def test_search_fails_closed_without_search_key_or_bad_query(monkeypatch):
    monkeypatch.delenv("DRAGONZPYDER_BRAVE_SEARCH_API_KEY", raising=False)
    with pytest.raises(SearchUnavailable):
        asyncio.run(search_sources("valid search", provider="brave"))
    with pytest.raises(ValueError):
        normalize_query("hello\ninjected")
    with pytest.raises(ValueError):
        asyncio.run(search_sources("good", provider="unknown"))


def test_monitor_diff_is_stable_for_reorder_and_evidence_changes():
    report = {"results": [
        {"title": "Second", "url": "https://example.org/b", "snippet": "B"},
        {"title": "First", "url": "https://example.org/a", "snippet": "A"},
    ]}
    first = canonical_sources(report)
    report["results"].reverse()
    assert first == canonical_sources(report)
    assert fingerprint(first) == fingerprint(canonical_sources(report))
    changed = [*first, {"title": "Third", "url": "https://example.org/c", "snippet": "C"}]
    diff = compare_sources(first, changed)
    assert diff["new"] == ["https://example.org/c"]
    assert diff["removed"] == []
    assert fingerprint(first) != fingerprint(changed)


def test_admin_schedule_rejects_per_minute_and_is_off_by_default(monkeypatch):
    for value in ("0 * * * *", "15 9 * * *", "15 9 * * 1", "0 */2 * * *"):
        assert validate_cron(value) == value
    for value in ("* * * * *", "*/5 * * * *", "0 */1 * * *", "60 9 * * *"):
        with pytest.raises(ValueError):
            validate_cron(value)
    for name in (
        "DRAGONZPYDER_MONITOR_ADMIN_ENABLED", "DRAGONZPYDER_WEB_MONITOR_ENABLED",
        "DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "DRAGONZPYDER_AGENT_HARNESS_V2",
        "DRAGONZPYDER_AGENT_WORKER_ALLOWED",
    ):
        monkeypatch.delenv(name, raising=False)
    assert not authorized()


def test_monitor_creates_baseline_then_detects_change(monkeypatch):
    monkeypatch.setenv("DRAGONZPYDER_WEB_MONITOR_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_DATABASE_URL", "postgresql://fake/fake")

    class FakeTx:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False

    class Conn:
        def __init__(self):
            self.row = None
        def transaction(self):
            return FakeTx()
        async def execute(self, sql, *args):
            if "INSERT INTO" in sql and self.row is None:
                self.row = {
                    "query_sha256": args[1], "fingerprint": "",
                    "sources_json": [], "checks": 0,
                }
            if "UPDATE dragonzpyder" in sql:
                self.row["fingerprint"] = args[1]
                self.row["sources_json"] = json.loads(args[2])
                self.row["checks"] += 1
            return "OK"
        async def fetchrow(self, sql, *args):
            return dict(self.row)
        async def close(self):
            pass

    conn = Conn()
    async def connect(*args, **kwargs):
        return conn

    state = {"snippet": "Original finding"}
    async def search(query, *, provider, limit):
        return {"results": [
            {"title": "Relevant article", "url": "https://example.org/a",
             "snippet": state["snippet"]},
        ]}

    input = MonitorInput(monitor_id="sample-monitor", query="interesting topic")
    async def do_checks():
        first = await run_monitor(input, search=search, connection_factory=connect)
        second = await run_monitor(input, search=search, connection_factory=connect)
        state["snippet"] = "Updated finding"
        third = await run_monitor(input, search=search, connection_factory=connect)
        return first, second, third
    first, second, third = asyncio.run(do_checks())
    assert first["status"] == "baseline_created" and not first["changed"]
    assert second["status"] == "unchanged" and not second["changed"]
    assert third["status"] == "changed" and third["changed"]
    assert third["diff"]["updated"] == ["https://example.org/a"]


def test_agent_web_search_is_flag_gated(monkeypatch):
    from agent_platform.web_research import web_search
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    result = asyncio.run(web_search.ainvoke({"query": "general information"}))
    assert "disabled" in result


def test_deepagents_web_tool_is_opt_in(monkeypatch):
    from agent_platform.harness import build_frontier_agent, specialist_specs
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import MemorySaver
    from agent_platform.web_research import web_search
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "1")
    specs = specialist_specs(search_tools=[web_search])
    assert {spec["name"] for spec in specs} == {"analyst", "builder", "verifier", "researcher"}
    assert specs[-1]["tools"] == [web_search]
    model = ChatOpenRouter(model="openai/gpt-oss-120b", api_key="test")
    graph = build_frontier_agent(model, MemorySaver())
    assert hasattr(graph, "ainvoke")


def test_searxng_general_search_uses_fixed_operator_origin(monkeypatch):
    from agent_platform.web_research import searxng_search_endpoint, resolve_provider
    monkeypatch.setenv("DRAGONZPYDER_SEARXNG_ORIGIN", "http://search.railway.internal:8080")
    assert searxng_search_endpoint() == "http://search.railway.internal:8080/search"
    monkeypatch.delenv("DRAGONZPYDER_BRAVE_SEARCH_API_KEY", raising=False)
    assert resolve_provider("auto") == "searxng"

    def fake(request):
        assert str(request.url).startswith("http://search.railway.internal:8080/search?")
        assert request.url.params["format"] == "json"
        assert request.url.params["q"] == "breaking developments in Nepal"
        return httpx.Response(200, json={"results": [
            {"title": "Current Nepal updates", "url": "https://example.org/nepal",
             "content": "Public current developments."},
            {"title": "Unsafe", "url": "http://127.0.0.1/admin", "content": "Nope"},
        ]})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
            return await search_sources(
                "breaking developments in Nepal", provider="searxng",
                limit=3, client=client
            )
    result = asyncio.run(go())
    assert result["source_scope"] == "general-web"
    assert len(result["results"]) == 1
    assert result["results"][0]["provider"] == "searxng"


def test_searxng_operator_origin_must_be_trusted(monkeypatch):
    from agent_platform.web_research import searxng_search_endpoint
    for bad in (
        "http://127.0.0.1:8080",
        "http://untrusted.example.org:8080",
        "http://search.railway.internal:8080/other",
        "http://evil@example.org",
        "file:///etc/passwd",
        "https://10.0.0.1",
    ):
        monkeypatch.setenv("DRAGONZPYDER_SEARXNG_ORIGIN", bad)
        with pytest.raises(SearchUnavailable):
            searxng_search_endpoint()


def test_source_read_pins_numeric_address_and_tls_hostname():
    from agent_platform.web_research import fetch_source
    async def resolver(host):
        assert host=="example.org"
        return ["93.184.216.34"]
    def transport(request):
        assert request.url.host=="93.184.216.34"
        assert request.url.path=="/article" and request.url.params["q"]=="test"
        assert request.headers["host"]=="example.org"
        assert request.extensions["sni_hostname"]=="example.org"
        assert "authorization" not in request.headers and "cookie" not in request.headers
        return httpx.Response(200,headers={"content-type":"text/html"},content=b"<html><script>IGNORE ME</script><p>Source text.</p></html>")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            return await fetch_source("https://example.org/article?q=test",resolver=resolver,client=client)
    result=asyncio.run(run())
    assert result["ok"] and result["text"]=="Source text." and len(result["source_sha256"])==64


def test_source_read_rejects_mixed_private_dns_redirect_and_large_response():
    from agent_platform.web_research import fetch_source,SourceReadUnavailable,MAX_SOURCE_BYTES
    calls=[]
    async def mixed(host):return ["93.184.216.34","127.0.0.1"]
    async def public(host):return ["93.184.216.34"]
    def redirected(request):
        calls.append(request.url.host)
        return httpx.Response(302,headers={"location":"https://127.0.0.1/secret"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(redirected),follow_redirects=False) as client:
            with pytest.raises(SourceReadUnavailable):await fetch_source("https://example.org/",resolver=mixed,client=client)
            assert calls==[]
            with pytest.raises(SourceReadUnavailable):await fetch_source("https://example.org/",resolver=public,client=client)
            assert calls==["93.184.216.34"]
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,headers={"content-type":"text/plain","content-length":str(MAX_SOURCE_BYTES+1)},content=b"x"))) as client:
            with pytest.raises(SourceReadUnavailable):await fetch_source("https://example.org/",resolver=public,client=client)
    asyncio.run(run())


def test_source_grants_are_run_scoped_and_single_attempt(monkeypatch):
    from agent_platform import web_research as w
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_FETCH_ENABLED","1")
    url="https://example.org/article"
    calls=[]
    async def search(query,**kwargs):return {"results":[{"url":url,"title":"Synthetic"}]}
    async def fetch(value):calls.append(value);return {"ok":True,"url":value,"text":"Synthetic source"}
    monkeypatch.setattr(w,"search_sources",search);monkeypatch.setattr(w,"fetch_source",fetch)
    async def run():
        a,b=w.scoped_research_tools();_,other=w.scoped_research_tools()
        assert "error" in json.loads(await b.ainvoke({"url":url}))
        report=json.loads(await a.ainvoke({"query":"synthetic source"}))
        assert report["sources_read"]==1 and report["source_reads"][0]["text"]=="Synthetic source"
        assert "error" in json.loads(await other.ainvoke({"url":url}))
        assert json.loads(await b.ainvoke({"url":url}))["ok"]
        assert json.loads(await b.ainvoke({"url":url}))["ok"]
        assert calls==[url]
    asyncio.run(run())
