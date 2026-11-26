"""Zero-provider, real LangGraph tool-loop acceptance tests.

These exercise actual Deep Agents filesystem dispatch and checkpoint state
with scripted AIMessage responses. They do NOT establish live model quality
or authorize host filesystem, network, or business tools.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from agent_platform.harness import build_frontier_agent
from agent_platform.runtime import summarize_agent_result


class ToolScript(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        # The harness still constructs and executes the real LangGraph tools.
        return self


def scripted_call(name: str, arguments: dict) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": name,
            "args": arguments,
            "id": "call_" + uuid4().hex,
            "type": "tool_call",
        }],
    )


def test_v2_real_virtual_write_read_and_checkpoint_roundtrip(monkeypatch):
    """A claimed file is insufficient; both real tool receipts must exist."""
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", raising=False)
    path = "/workspace/acceptance.txt"
    expected = "DRAGONZPYDER_TOOL_RECEIPT_391"
    model = ToolScript(responses=[
        scripted_call("write_file", {"file_path": path, "content": expected}),
        scripted_call("read_file", {"file_path": path}),
        AIMessage(content="The file was written and read back."),
    ])
    checkpointer = MemorySaver()
    config = {"configurable": {"thread_id": "acceptance-tool-roundtrip"}}

    async def run():
        agent = build_frontier_agent(model, checkpointer)
        state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Write and read the test file."}]},
            config=config,
        )
        report = summarize_agent_result(state)
        assert report["status"] == "completed"
        assert "write_file" in report["successful_tools"]
        assert "read_file" in report["successful_tools"]
        assert path in report["virtual_artifact_paths"]
        assert path in report["artifact_readback_paths"]
        assert expected in str(state["files"][path])
        # Reconstructing the graph must not erase the checkpointed file.
        another_agent = build_frontier_agent(
            ToolScript(responses=[AIMessage(content="No action needed.")]),
            checkpointer,
        )
        snapshot = await another_agent.aget_state(config)
        assert path in snapshot.values["files"]
        assert expected in str(snapshot.values["files"][path])
        # Tool dispatch and checkpoint alone cannot certify objective correctness.
        assert report["objective_verified"] is False

    asyncio.run(run())


def test_v2_rejects_virtual_filesystem_escape(monkeypatch):
    """An agent-issued write outside /workspace must not persist."""
    monkeypatch.delenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", raising=False)
    target = "/private/credentials.txt"
    model = ToolScript(responses=[
        scripted_call("write_file", {"file_path": target, "content": "do-not-write"}),
        AIMessage(content="Cannot write outside the authorized virtual workspace."),
    ])

    async def run():
        agent = build_frontier_agent(model, MemorySaver())
        state = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Write to a forbidden path."}]},
            config={"configurable": {"thread_id": "acceptance-denied-write"}},
        )
        assert target not in state.get("files", {})
        # A denial must not be counted as a verified external action.
        report = summarize_agent_result(state)
        assert report["objective_verified"] is False

    asyncio.run(run())


def test_simulated_business_tools_real_graph_approval_and_replay(monkeypatch):
    """Actual LangGraph dispatch: read, preview, reject, commit, replay, verify."""
    import json
    from langchain_core.messages import ToolMessage
    from agent_platform.synthetic_business_tools import SyntheticBusiness

    monkeypatch.setenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "0")
    fake = SyntheticBusiness()
    fake.approvals.add("approved-test-1")
    model = ToolScript(responses=[
        scripted_call("lookup_inventory", {"sku": "coffee"}),
        scripted_call("simulate_order", {"sku": "coffee", "quantity": 2}),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "missing",
        }),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "approved-test-1",
        }),
        scripted_call("commit_order", {
            "sku": "coffee", "quantity": 2, "request_id": "order-1",
            "approval_id": "approved-test-1",
        }),
        scripted_call("lookup_order", {"request_id": "order-1"}),
        AIMessage(content="Simulated order completed; readback confirmed."),
    ])
    async def run():
        graph = build_frontier_agent(model, MemorySaver(), synthetic_tools=fake.tools())
        state = await graph.ainvoke(
            {"messages": [{"role": "user", "content": "Run simulated inventory workflow."}]},
            config={"configurable": {"thread_id": "synthetic-business-roundtrip"}},
        )
        receipts = [json.loads(m.content) for m in state["messages"]
                    if isinstance(m, ToolMessage) and m.name in {
                        "lookup_inventory", "simulate_order", "commit_order", "lookup_order"}]
        assert len(receipts) == 6
        assert receipts[0]["quantity"] == 7
        assert receipts[1]["requires_approval"] is True
        assert receipts[2]["code"] == "approval_required"
        assert receipts[3]["ok"] and receipts[3]["replayed"] is False
        assert receipts[4]["ok"] and receipts[4]["replayed"] is True
        assert receipts[5]["receipt"]["request_id"] == "order-1"
        assert fake.inventory["coffee"] == 5
        assert len(fake.receipts) == 1
        report = summarize_agent_result(state)
        assert report["objective_verified"] is False
        assert "commit_order" in report["successful_tools"]
    asyncio.run(run())


def test_simulated_business_denials_and_transient_recovery():
    """The simulated provider, not the model, enforces permissions and dedup."""
    import json
    from agent_platform.synthetic_business_tools import SyntheticBusiness
    fake = SyntheticBusiness(fail_next_commit=True)
    tools = {tool.name: tool for tool in fake.tools()}

    async def call(name, args):
        return json.loads(await tools[name].ainvoke(args))

    async def run():
        base = {"sku": "coffee", "quantity": 2, "request_id": "r-77",
                "approval_id": "auth-77"}
        denied = await call("commit_order", base)
        assert denied["code"] == "approval_required"
        assert fake.inventory["coffee"] == 7
        fake.approvals.add("auth-77")
        failure = await call("commit_order", base)
        assert failure["code"] == "transient_failure" and failure["retryable"]
        assert fake.inventory["coffee"] == 7
        accepted = await call("commit_order", base)
        assert accepted["ok"] and not accepted["replayed"]
        replay = await call("commit_order", base)
        assert replay["ok"] and replay["replayed"]
        conflict = await call("commit_order", {**base, "quantity": 3})
        assert conflict["code"] == "idempotency_conflict"
        assert fake.inventory["coffee"] == 5
        assert len(fake.receipts) == 1
    asyncio.run(run())


def test_synthetic_tools_must_be_explicitly_enabled(monkeypatch):
    import pytest
    from agent_platform.synthetic_business_tools import SyntheticBusiness
    monkeypatch.delenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED", raising=False)
    with pytest.raises(ValueError, match="disabled"):
        build_frontier_agent(
            ToolScript(responses=[AIMessage(content="no action")]),
            MemorySaver(), synthetic_tools=SyntheticBusiness().tools(),
        )


def test_operly_real_graph_discover_execute_verify_with_http_broker(monkeypatch):
    """Actual Deep Agents tool loop using native HTTP broker contract (stub transport).

    Operly's separate CI verifies the real broker/Kernel/database contract.
    This test verifies model-to-transport orchestration; no live model or secrets.
    """
    import httpx
    import json
    from langchain_core.messages import ToolMessage
    from agent_platform.operly_readonly_tools import OperlyReadOnlyTools

    monkeypatch.setenv("DRAGONZPYDER_OPERLY_TOOLS_ENABLED", "1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED", "0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED", "0")
    calls = []

    def handler(request):
        calls.append((request.url.path, json.loads(request.content)))
        assert request.headers["x-operly-agent-lease"] == "lease-for-test"
        assert request.headers["authorization"] == "Bearer " + "s" * 48
        if request.url.path.endswith("/search"):
            query = calls[-1][1]["query"]
            spec = {
                "system.runtime.status": {
                    "id": "system.runtime.status", "risk": "read_only",
                    "description": "Runtime status", "input_schema": {
                        "type": "object", "properties": {},
                    },
                },
                "tasks.list": {
                    "id": "tasks.list", "risk": "read_only",
                    "description": "List personal tasks", "input_schema": {
                        "type": "object", "properties": {"limit": {"type": "integer"}},
                    },
                },
            }
            name = "tasks.list" if "tasks" in query else "system.runtime.status"
            return httpx.Response(200, json={"source": "operly", "tools": [spec[name]]})
        if request.url.path.endswith("/execute"):
            action = calls[-1][1]["capability_id"]
            if action == "tasks.list":
                return httpx.Response(200, json={"ok": True, "result": {
                    "tasks": [{"title": "Synthetic project follow-up", "status": "open"}]}})
            if action == "system.runtime.status":
                return httpx.Response(200, json={"ok": True, "result": {
                    "kernel_runtime_enabled": True, "scope_kind": "personal"}})
        raise AssertionError("Unexpected broker request")

    model = ToolScript(responses=[
        scripted_call("operly_search", {"query": "my tasks"}),
        scripted_call("operly_execute", {
            "capability_id": "tasks.list", "arguments": {"limit": 5},
        }),
        scripted_call("operly_search", {"query": "runtime status"}),
        scripted_call("operly_execute", {
            "capability_id": "system.runtime.status", "arguments": {},
        }),
        AIMessage(content="One synthetic open task; runtime is enabled."),
    ])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            broker = OperlyReadOnlyTools(
                client=client, origin="https://operly.dragonzpyder.xyz",
                service_token="s" * 48, lease="lease-for-test",
            )
            graph = build_frontier_agent(
                model, MemorySaver(), delegated_tools=broker.langchain_tools(),
            )
            state = await graph.ainvoke({
                "messages": [{"role": "user", "content": "Find open tasks and runtime status"}],
            }, config={"configurable": {"thread_id": "native-platform-tool-acceptance"}})
            replies = [json.loads(m.content) for m in state["messages"]
                       if isinstance(m, ToolMessage) and m.name in {
                           "operly_search", "operly_execute"}]
            assert len(replies) == 4
            assert all(reply["ok"] for reply in replies)
            assert replies[1]["result"]["tasks"][0]["title"] == "Synthetic project follow-up"
            assert replies[3]["result"]["kernel_runtime_enabled"]
            assert [path.rsplit("/", 1)[-1] for path, _ in calls] == [
                "search", "execute", "search", "execute"]
            assert summarize_agent_result(state)["objective_verified"] is False
    asyncio.run(run())


def test_operly_broker_requires_discovery_and_fails_closed(monkeypatch):
    import json
    import httpx
    import pytest
    from agent_platform.operly_readonly_tools import (
        OperlyReadOnlyTools, OperlyBrokerError,
    )
    monkeypatch.delenv("DRAGONZPYDER_OPERLY_TOOLS_ENABLED", raising=False)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(
                AssertionError("Broker should not be called"))
        )) as client:
            broker = OperlyReadOnlyTools(
                client=client, origin="https://operly.dragonzpyder.xyz",
                service_token="s" * 48, lease="lease-for-test", max_calls=1,
            )
            tools = {t.name: t for t in broker.langchain_tools()}
            denied = json.loads(await tools["operly_execute"].ainvoke({
                "capability_id": "tasks.create", "arguments": {"title": "unsafe"},
            }))
            assert denied["error_code"] == "capability_not_discovered"
            with pytest.raises(ValueError, match="disabled"):
                build_frontier_agent(
                    ToolScript(responses=[AIMessage(content="No action")]),
                    MemorySaver(), delegated_tools=broker.langchain_tools(),
                )
            with pytest.raises(OperlyBrokerError):
                OperlyReadOnlyTools(
                    client=client, origin="http://attacker.example",
                    service_token="s" * 48, lease="lease-for-test",
                )
    asyncio.run(run())


def test_hatchet_delegates_via_api_and_rejects_bad_auth(monkeypatch):
    """Actual HTTP request shape with no external network or paid inference."""
    import json
    import httpx
    import pytest
    from agent_platform.jobs import AgentJobInput, delegate_agent_job_to_api
    monkeypatch.setenv("DRAGONZPYDER_AGENT_SERVICE_TOKEN", "z" * 48)
    monkeypatch.setenv("DRAGONZPYDER_HATCHET_AGENT_API_URL",
                       "http://dragonzpyder-api.railway.internal:8080/internal/agents/run")
    seen = []

    def handler(request):
        seen.append((request.url.path, json.loads(request.content)))
        assert request.headers["authorization"] == "Bearer " + "z" * 48
        data = json.loads(request.content)
        return httpx.Response(200, json={
            "thread_id": data["thread_id"], "answer": "API result"
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await delegate_agent_job_to_api(
                AgentJobInput(thread_id="scheduled-test-1", prompt="Inspect test state"),
                client=client,
            )
            assert result["answer"] == "API result"
        assert len(seen) == 1
        monkeypatch.setenv("DRAGONZPYDER_HATCHET_AGENT_API_URL",
                           "https://bad-host.example/internal/agents/run")
        with pytest.raises(RuntimeError, match="not configured"):
            await delegate_agent_job_to_api(
                AgentJobInput(thread_id="scheduled-test-2", prompt="Do not execute"))
    asyncio.run(run())


def test_hatchet_cron_registration_is_explicit_and_staging_only(monkeypatch):
    """Uses Hatchet's own cron API, never installs an implicit recurring job."""
    import pytest
    from agent_platform.jobs import install_staging_agent_ping_cron, PingInput
    class FakeHatchetTask:
        def __init__(self):
            self.calls = []
        async def aio_create_cron(self, **kwargs):
            self.calls.append(kwargs)
            return {"ok": True}
    fake = FakeHatchetTask()

    async def run():
        monkeypatch.delenv("DRAGONZPYDER_STAGING_HATCHET_PING_CRON_ALLOWED",
                           raising=False)
        monkeypatch.setenv("DRAGONZPYDER_STAGE", "staging")
        with pytest.raises(RuntimeError, match="not authorized"):
            await install_staging_agent_ping_cron(fake)
        monkeypatch.setenv("DRAGONZPYDER_STAGING_HATCHET_PING_CRON_ALLOWED", "1")
        await install_staging_agent_ping_cron(fake)
        assert len(fake.calls) == 1
        assert fake.calls[0]["expression"] == "*/5 * * * *"
        assert isinstance(fake.calls[0]["input"], PingInput)
        monkeypatch.setenv("DRAGONZPYDER_STAGE", "production")
        with pytest.raises(RuntimeError, match="not authorized"):
            await install_staging_agent_ping_cron(fake)
        assert len(fake.calls) == 1
    asyncio.run(run())


def test_native_computer_tools_execute_multistep_graph_with_scoped_mock_runner(monkeypatch):
    """Actual Deep Agents graph, simulated VM transport; no allocation or model spend."""
    from agent_platform.computer import ComputerScope
    from agent_platform.computer_run import ComputerRun, ComputerRunGrant, computer_tools
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.memory import MemorySaver

    scope = ComputerScope("personal","owner-123","task-123")
    class Runner:
        files = {}
        calls = []
        async def create(self, **kwargs):
            assert kwargs["scope"] == scope
            self.calls.append("create")
            return {"id":"vm-123"}
        async def execute_authorized(self, *, sandbox_id, scope, tool_id, args):
            assert sandbox_id == "vm-123" and scope.principal_id == "owner-123"
            self.calls.append(tool_id)
            if tool_id == "files.write":
                self.files[args["path"]] = args["content"]
                return {"ok":True,"path":args["path"]}
            if tool_id == "python.exec":
                assert self.files["input.txt"] == "41"
                self.files["output.txt"] = "42"
                return {"ok":True,"exit_code":0,"stdout":"42"}
            if tool_id == "files.read":
                return {"ok":True,"content":self.files[args["path"]]}
            raise AssertionError(tool_id)
        async def destroy_authorized(self, sandbox_id, *, scope):
            assert sandbox_id == "vm-123" and scope.principal_id == "owner-123"
            self.calls.append("destroy")
            return {"destroyed":True}

    async def scenario():
        runner = Runner()
        run = ComputerRun(runner,ComputerRunGrant(scope,max_calls=3))
        graph = build_frontier_agent(ToolScript(responses=[
            scripted_call("computer_write_file",{"path":"input.txt","content":"41"}),
            scripted_call("computer_python",{"code":"from pathlib import Path; Path('output.txt').write_text(str(int(Path('input.txt').read_text())+1))"}),
            scripted_call("computer_read_file",{"path":"output.txt"}),
            AIMessage(content="The computed output is 42."),
        ]),MemorySaver(),computer_run=run)
        assert runner.calls == []
        try:
            result = await graph.ainvoke(
                {"messages":[{"role":"user","content":"Compute and inspect the result"}]},
                config={"configurable":{"thread_id":"offline-computer-run"},"recursion_limit":128})
            messages = [m for m in result["messages"] if isinstance(m,ToolMessage)]
            assert len(messages) == 3 and all(m.status == "success" for m in messages)
            assert runner.files["output.txt"] == "42"
            assert "vm-123" not in str(messages)
            assert result["messages"][-1].content == "The computed output is 42."
        finally:
            assert await run.close()
        assert runner.calls == ["create","files.write","python.exec","files.read","destroy"]

    monkeypatch.setenv("DRAGONZPYDER_SYNTHETIC_TOOLS_ENABLED","1")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_WEB_SEARCH_ENABLED","0")
    monkeypatch.setenv("DRAGONZPYDER_AGENT_QUICKJS_ENABLED","0")
    asyncio.run(scenario())


def test_computer_run_never_replays_uncertain_allocation_and_cleans_known_session():
    from agent_platform.computer import ComputerScope
    from agent_platform.computer_run import ComputerRun, ComputerRunGrant
    import pytest
    scope = ComputerScope("personal","owner-123","task-123")
    class Runner:
        creates=0
        calls=0
        destroys=0
        async def create(self,**kwargs):
            self.creates+=1
            return {"id":"vm-123"}
        async def execute_authorized(self,**kwargs):
            self.calls+=1
            raise TimeoutError()
        async def destroy_authorized(self,*args,**kwargs):
            self.destroys+=1
            return {"destroyed":True}
    async def scenario():
        transport=Runner()
        run=ComputerRun(transport,ComputerRunGrant(scope))
        with pytest.raises(TimeoutError):
            await run.execute("python.exec",{"code":"print(1)"})
        with pytest.raises(RuntimeError):
            await run.execute("python.exec",{"code":"print(1)"})
        assert await run.close()
        assert await run.close()
        assert (transport.creates,transport.calls,transport.destroys)==(1,1,1)

        class LostAllocation(Runner):
            async def create(self,**kwargs):
                self.creates+=1
                raise TimeoutError()
        lost=LostAllocation()
        run=ComputerRun(lost,ComputerRunGrant(scope))
        with pytest.raises(TimeoutError):
            await run.execute("files.list",{})
        with pytest.raises(RuntimeError):
            await run.execute("files.list",{})
        assert not await run.close()
        assert (lost.creates,lost.calls,lost.destroys)==(1,0,0)
    asyncio.run(scenario())
