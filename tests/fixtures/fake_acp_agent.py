"""Fake ACP agent for tests: speaks ACP over stdio with the official SDK.

It never calls a model. One prompt turn sends a plan, streamed text, a read
tool call, the attached AgentEng MCP tool (when FAKE_ACP_USE_MCP=1) and an edit
that needs permission. FAKE_ACP_RECORD names a JSON file that records what the
client sent. FAKE_ACP_MODE=auth makes session/new demand sign-in.
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
        record(prompt=texts)
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

        edit = acp.start_edit_tool_call(
            "edit-1", "Write demo/README.md", "demo/README.md", "# Demo\n"
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
            ),
            options=options,
        )
        outcome = response.outcome
        chosen = getattr(outcome, "option_id", None)
        record(permission_outcome=outcome.outcome, permission_option=chosen)
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

    async def cancel(self, session_id, **kw):
        record(cancelled=session_id)


if __name__ == "__main__":
    asyncio.run(acp.run_agent(FakeAgent()))
