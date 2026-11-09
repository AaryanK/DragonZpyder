"""Sanitized, meaningful LangChain tool activity without prompt leakage."""
import asyncio
from uuid import uuid4
from agent_platform.web_task_worker import ActivityTrace


class Events:
    def __init__(self):
        self.events = []

    async def append(self, task_id, kind, message):
        self.events.append((task_id, kind, message))


def test_known_tool_name_visible_without_prompts_arguments_or_outputs():
    async def run():
        store = Events()
        task = str(uuid4())
        callbacks = ActivityTrace(store, task).handler()
        rid = uuid4()
        await callbacks.on_tool_start(
            {"name": "read_file"}, "SECRET FILE PATH /home/private.txt",
            run_id=rid,
        )
        await callbacks.on_tool_end("CONFIDENTIAL CONTENT", run_id=rid)
        assert store.events == [
            (task, "tool_started", "Read file started"),
            (task, "tool_finished", "Read file completed"),
        ]
        assert "SECRET" not in str(store.events)
        assert "CONFIDENTIAL" not in str(store.events)
    asyncio.run(run())


def test_unknown_tool_metadata_cannot_inject_private_content_into_events():
    async def run():
        store = Events()
        task = str(uuid4())
        handler = ActivityTrace(store, task).handler()
        rid = uuid4()
        await handler.on_tool_start(
            {"name": "send_gmail_to_secret_person@example.com"},
            "{'oauth_secret':'PRIVATE_KEY'}", run_id=rid,
        )
        await handler.on_tool_error(Exception("token: SECRET"), run_id=rid)
        assert store.events == [
            (task, "tool_started", "Tool started"),
            (task, "info", "Tool returned an error"),
        ]
    asyncio.run(run())
