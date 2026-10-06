"""Fake ACP agent for tests: speaks ACP over stdio with the official SDK.

It never calls a model. The first prompt turn sends a plan, streamed text, the
attached AgentEng MCP tool (when FAKE_ACP_USE_MCP=1) and an edit with ACP diff
content that needs permission. Later turns echo the prompt; a prompt containing
"patch" streams an edit whose diff arrives on tool_call_update without asking.
FAKE_ACP_RECORD names a JSON file that records what the client sent.
FAKE_ACP_MODE=auth makes session/new demand sign-in; FAKE_ACP_MODE=slow makes a
turn wait until session/cancel. FAKE_ACP_DIFF_LINES=N makes the edit diff long.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import acp
from acp import schema


def record(**data) -> None:
    path = os.environ.get("FAKE_ACP_RECORD")
    if not path:
        return
    target = Path(path)
    current = json.loads(target.read_text()) if target.exists() else {}
    current.update(data)
    target.write_text(json.dumps(current, indent=2))


async def call_agenteng_mcp(server: schema.McpServerStdio, session_id: str) -> str:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=server.command,
        args=list(server.args),
        env={**os.environ, **{e.name: e.value for e in server.env}},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [tool.name for tool in (await session.list_tools()).tools]
            result = await session.call_tool(
                "agenteng", {"request": {"operation": "talk", "session_id": session_id}}
            )
            data = result.structuredContent or {}
            record(mcp_tools=tools, mcp_status=data.get("status"))
            return (data.get("data") or {}).get("title", "")


class FakeAgent(acp.Agent):
    def __init__(self):
        self.conn = None
        self.sessions: dict[str, list] = {}
        self.turn = 0
        self.prompts: list[list[str]] = []
        self.cancelled = asyncio.Event()

    def on_connect(self, conn) -> None:
        self.conn = conn

    async def initialize(self, protocol_version, client_capabilities=None, client_info=None, **kw):
        record(
            protocol_version=protocol_version,
            client_capabilities=client_capabilities.model_dump(mode="json", by_alias=True)
            if client_capabilities
            else None,
            client_info=client_info.model_dump(mode="json") if client_info else None,
        )
        return schema.InitializeResponse(
            protocol_version=acp.PROTOCOL_VERSION,
            agent_capabilities=schema.AgentCapabilities(load_session=False),
            agent_info=schema.Implementation(
                name="fake-acp-agent", title="Fake ACP agent", version="0.1"
            ),
        )

    async def new_session(self, cwd, additional_directories=None, mcp_servers=None, **kw):
        if os.environ.get("FAKE_ACP_MODE") == "auth":
            raise acp.RequestError.auth_required()
        servers = list(mcp_servers or [])
        record(cwd=cwd, mcp_servers=[s.model_dump(mode="json") for s in servers])
        self.sessions["fake-session-1"] = servers
        return schema.NewSessionResponse(session_id="fake-session-1")

    async def send(self, session_id, update) -> None:
        await self.conn.session_update(session_id=session_id, update=update)

    async def prompt(self, session_id, prompt, **kw):
        texts = [getattr(block, "text", "") for block in prompt]
        self.turn += 1
        self.prompts.append(texts)
        record(prompt=texts, prompts=self.prompts, turns=self.turn)
        self.cancelled.clear()
        if os.environ.get("FAKE_ACP_MODE") == "slow":
            await self.send(session_id, acp.update_agent_message_text("Working on it"))
            try:
                await asyncio.wait_for(self.cancelled.wait(), 20)
            except asyncio.TimeoutError:
                return schema.PromptResponse(stop_reason="end_turn")
            return schema.PromptResponse(stop_reason="cancelled")
        if self.turn > 1:
            return await self.later_turn(session_id, texts)
        await self.send(
            session_id,
            acp.update_plan(
                [
                    acp.plan_entry("Read the talk from AgentEng", status="in_progress"),
                    acp.plan_entry("Write demo/README.md", status="pending"),
                ]
            ),
        )
        await self.send(session_id, acp.update_agent_thought_text("Thinking about the talk."))
        for chunk in ("Looking up the talk ", "with AgentEng.\n"):
            await self.send(session_id, acp.update_agent_message_text(chunk))

        title = ""
        servers = self.sessions.get(session_id) or []
        if os.environ.get("FAKE_ACP_USE_MCP") == "1" and servers:
            await self.send(
                session_id,
                acp.start_tool_call("mcp-1", "agenteng: talk", kind="fetch", status="in_progress"),
            )
            title = await call_agenteng_mcp(
                servers[0], os.environ.get("FAKE_ACP_TALK", "agenteng-london-2026-14")
            )
            await self.send(session_id, acp.update_tool_call("mcp-1", status="completed"))
            await self.send(session_id, acp.update_agent_message_text(f"Talk: {title}\n"))

        edit = schema.ToolCallStart(
            session_update="tool_call",
            tool_call_id="edit-1",
            title="Write demo/README.md",
            kind="edit",
            status="pending",
            locations=[schema.ToolCallLocation(path="demo/README.md")],
            content=[demo_diff()],
        )
        await self.send(session_id, edit)
        options = [
            schema.PermissionOption(option_id="allow", name="Allow", kind="allow_once"),
            schema.PermissionOption(option_id="always", name="Always allow", kind="allow_always"),
            schema.PermissionOption(option_id="reject", name="Reject", kind="reject_once"),
        ]
        response = await self.conn.request_permission(
            session_id=session_id,
            tool_call=schema.ToolCallUpdate(
                tool_call_id="edit-1",
                title="Write demo/README.md",
                kind="edit",
                locations=[schema.ToolCallLocation(path="demo/README.md")],
                content=[demo_diff()],
            ),
            options=options,
        )
        outcome = response.outcome
        chosen = getattr(outcome, "option_id", None)
        record(permission_outcome=outcome.outcome, permission_option=chosen)
        if outcome.outcome == "cancelled" or self.cancelled.is_set():
            return schema.PromptResponse(stop_reason="cancelled")
        allowed = chosen in ("allow", "always")
        await self.send(
            session_id, acp.update_tool_call("edit-1", status="completed" if allowed else "failed")
        )
        await self.send(
            session_id,
            acp.update_plan(
                [
                    acp.plan_entry("Read the talk from AgentEng", status="completed"),
                    acp.plan_entry(
                        "Write demo/README.md", status="completed" if allowed else "pending"
                    ),
                ]
            ),
        )
        await self.send(
            session_id,
            acp.update_agent_message_text(
                "Wrote the demo.\n" if allowed else "Skipped the write.\n"
            ),
        )
        return schema.PromptResponse(stop_reason="end_turn")

    async def later_turn(self, session_id, texts):
        text = texts[-1]
        attached = [t.split("`")[1] for t in texts[:-1] if t.startswith("AgentEng ")]
        if attached:
            await self.send(
                session_id, acp.update_agent_message_text(f"Using context: {', '.join(attached)}\n")
            )
        if "patch" in text.lower():
            await self.send(
                session_id,
                acp.start_tool_call(
                    "edit-2", "Patch demo/app.py", kind="edit", status="in_progress"
                ),
            )
            await self.send(
                session_id,
                schema.ToolCallProgress(
                    session_update="tool_call_update",
                    tool_call_id="edit-2",
                    status="completed",
                    content=[
                        schema.FileEditToolCallContent(
                            type="diff",
                            path="demo/app.py",
                            old_text='print("hello")\n',
                            new_text='from memory import recall\n\nprint(recall("hello"))\n',
                        )
                    ],
                ),
            )
        await self.send(session_id, acp.update_agent_message_text(f"Turn {self.turn}: {text}\n"))
        return schema.PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id, **kw):
        record(cancelled=session_id)
        self.cancelled.set()


def demo_diff() -> schema.FileEditToolCallContent:
    lines = int(os.environ.get("FAKE_ACP_DIFF_LINES", "0") or 0)
    new = "# Demo\n\nMemory engineering demo for talk agenteng-london-2026-14.\n\n"
    new += "## Run\n\n    uv run demo.py\n"
    new += "".join(f"line {i}\n" for i in range(lines))
    return schema.FileEditToolCallContent(
        type="diff", path="demo/README.md", old_text="# Demo\nTODO\n", new_text=new
    )


if __name__ == "__main__":
    asyncio.run(acp.run_agent(FakeAgent()))
