"""Official A2A 1.0 SDK adapter; immediate responses with no retained conversations."""

import json
from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    Message,
    Part,
    HTTPAuthSecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)
from a2a.utils.errors import InvalidParamsError, UnsupportedOperationError
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value
from pydantic import ValidationError

from .auth import bearer
from .models import Request


def agent_card(service):
    private_skills = []
    security_schemes = {}
    if service.settings.enable_intake:
        security_schemes["participant"] = SecurityScheme(
            http_auth_security_scheme=HTTPAuthSecurityScheme(
                scheme="bearer",
                description="Organizer-issued, per-participant pilot credential. "
                "Not the optional inference operator credential.",
            )
        )
        private_skills.append(
            AgentSkill(
                id="agenteng-participation",
                name="Private Agent Engineering HQ participation",
                description="Prepare an exact private preview, explicitly confirm submission, read your receipt or withdraw. "
                "Requires participant access. No review, response, acceptance or event is guaranteed. "
                "Submission content is never published automatically.",
                tags=["proposals", "London", "San Francisco", "private-intake"],
                security_requirements=[
                    SecurityRequirement(schemes={"participant": StringList(list=[])})
                ],
            )
        )
    return AgentCard(
        name="Agent Engineering HQ: AgentEng Conference",
        description="AgentEng, the Agent Engineering Conference, and Agent Engineering HQ technical events in London and San Francisco. Discover published dates, speakers, full talk abstracts, agendas, FAQ, venue, sponsors, code of conduct, registration links, proposal drafting and a tool directory across twelve agent-engineering disciplines. Anonymous requests use catalogue lookup with no model calls. London 2026 has an invited programme and no public CFP.",
        version="1.0",
        provider=AgentProvider(
            organization="Agent Engineering HQ", url="https://agentengineering.world"
        ),
        documentation_url=service.settings.public_url + "/docs",
        supported_interfaces=[
            AgentInterface(
                url=service.settings.public_url + "/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False, push_notifications=False, extended_agent_card=False
        ),
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json", "text/plain"],
        security_schemes=security_schemes,
        skills=[
            AgentSkill(
                id="agenteng",
                name="AgentEng London and San Francisco events",
                description="Use a typed AgentEng request or a public-event search question. Returns evidence, date precision and snapshot freshness.",
                tags=[
                    "events",
                    "conferences",
                    "agent-engineering",
                    "AgentEng",
                    "Agent Engineering HQ",
                    "Agent Engineering Conference",
                    "London",
                    "San Francisco",
                    "coding-agents",
                    "mcp",
                    "a2a",
                ],
                examples=[
                    '{"operation":"events","upcoming":true}',
                    '{"operation":"discover"}',
                    '{"operation":"tickets","event_id":"agenteng-london-2026"}',
                    '{"operation":"proposal_draft","draft":{"city":"San Francisco","kind":"event_idea","title":"Agent evaluation workshop"}}',
                ],
            ),
            AgentSkill(
                id="agenteng-event-day",
                name="AgentEng event day and about",
                description="Venue-screen now/next snapshots (live, with an optional at time), "
                "reproducible talk bingo cards from published talk terms (bingo with seed, size 4 "
                "or 5, format json/text/svg/html), the organiser and chair card (about) and the "
                "Agent Engineering HQ manifesto, mindset and further reading (hq). Model-free.",
                tags=["live", "now-next", "bingo", "about", "manifesto", "Agent Engineering HQ"],
                examples=[
                    '{"operation":"live","event_id":"agenteng-london-2026"}',
                    '{"operation":"bingo","seed":2026,"size":5}',
                    '{"operation":"about","section":"connect"}',
                    '{"operation":"hq","section":"manifesto"}',
                ],
            ),
            AgentSkill(
                id="agenteng-tools",
                name="Agent-engineering tool directory",
                description="Browse public tool names and links across twelve disciplines using "
                "disciplines, tools and tool. Filter by discipline, kind, category or query; paginate "
                "with limit/offset and next_offset. Offline, model-free listings with source provenance; "
                "no popularity rankings, installations or vendor integrations are implied.",
                tags=[
                    "tools",
                    "agent-engineering",
                    "disciplines",
                    "memory",
                    "inference",
                    "protocol",
                ],
                examples=[
                    '{"operation":"disciplines"}',
                    '{"operation":"tools","discipline":"memory"}',
                    '{"operation":"tool","tool_id":"langgraph"}',
                ],
            ),
        ]
        + private_skills,
    )


class Executor(AgentExecutor):
    def __init__(self, service):
        self.service = service

    async def execute(self, context, event_queue):
        message = context.message
        if message is None:
            raise InvalidParamsError("A user message is required.")
        if any(p.HasField("raw") or p.HasField("url") for p in message.parts):
            raise InvalidParamsError("Only JSON request data or text input is supported.")
        data_parts = [p for p in message.parts if p.HasField("data")]
        try:
            if data_parts:
                if len(data_parts) != 1 or any(p.HasField("text") for p in message.parts):
                    raise ValueError("Send one JSON request part.")
                request = Request.model_validate(MessageToDict(data_parts[0].data))
            else:
                text = context.get_user_input().strip()
                request = (
                    Request.model_validate_json(text)
                    if text.startswith("{")
                    else Request(operation="ask", query=text)
                )
        except (ValueError, ValidationError) as exc:
            raise InvalidParamsError(
                "Invalid AgentEng request; use the documented request schema."
            ) from exc
        call_context = context.call_context
        headers = call_context.state.get("headers", {}) if call_context else {}
        result = await self.service.execute(request, token=bearer(headers))
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                context_id=context.context_id,
                role=2,
                parts=[
                    Part(text=result.answer),
                    Part(
                        data=ParseDict(json.loads(result.model_dump_json()), Value()),
                        media_type="application/json",
                    ),
                ],
            )
        )

    async def cancel(self, context, event_queue):
        raise UnsupportedOperationError(
            "This agent returns immediate messages; persistent tasks are not supported."
        )


def add_a2a(app, service):
    card = agent_card(service)
    handler = DefaultRequestHandler(Executor(service), InMemoryTaskStore(), card)
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(handler, rpc_url="/"),
    )
    return card
