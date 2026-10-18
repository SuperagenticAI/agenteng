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
)
from a2a.utils.errors import InvalidParamsError, UnsupportedOperationError
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Value
from pydantic import ValidationError

from .auth import bearer
from .models import Request


def agent_card(service):
    return AgentCard(
        name="Agent Engineering HQ: AgentEng Conference",
        description="AgentEng, the Agent Engineering Conference, and Agent Engineering HQ technical events in London and San Francisco. Discover published dates, speakers, full talk abstracts, agendas, FAQ, venue, sponsors, code of conduct, registration links and a tool directory across twelve agent-engineering disciplines. Catalogue lookups use no model calls. The opt-in chat operation uses public catalogue tools and falls back to lookup when inference is unavailable. London 2026 has an invited programme and no public CFP.",
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
        skills=[
            AgentSkill(
                id="agenteng-chat",
                name="Public AgentEng chat",
                description="Ask a question with optional recent history. When enabled by the "
                "operator, chat uses a model with bounded public catalogue lookups. Disabled "
                "or unavailable inference returns the existing catalogue answer automatically.",
                tags=["chat", "public-catalogue", "lookup-fallback"],
                examples=['{"operation":"chat","query":"Who is speaking in London?"}'],
            ),
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
                    '{"operation":"venue","event_id":"agenteng-london-2026"}',
                ],
            ),
            AgentSkill(
                id="agenteng-event-day",
                name="AgentEng event day and about",
                description="The published London day guide (guide; optional section such as "
                "arriving, getting-here, registration, qna or help, or section list for the index) "
                "with arrival times, directions and help contacts, "
                "venue-screen now/next snapshots (live, with an optional at time), "
                "reproducible talk bingo cards from published talk terms (bingo with seed, size 4 "
                "or 5; the card is always in data, and format text, svg or html also returns a "
                "printable copy in artifact), the organiser and chair card (about) and the "
                "Agent Engineering HQ manifesto, mindset and further reading (hq). Model-free.",
                tags=[
                    "guide",
                    "day-guide",
                    "live",
                    "now-next",
                    "bingo",
                    "about",
                    "manifesto",
                    "Agent Engineering HQ",
                ],
                examples=[
                    '{"operation":"guide","section":"arriving"}',
                    '{"operation":"live","event_id":"agenteng-london-2026"}',
                    '{"operation":"bingo","seed":2026,"size":5}',
                    '{"operation":"about","section":"connect"}',
                    '{"operation":"hq","section":"manifesto"}',
                ],
            ),
            AgentSkill(
                id="agenteng-gallery",
                name="Video gallery",
                description="The website video gallery (gallery; optional city, event_id, topic, "
                "query and speaker_id), mirroring /gallery: the AgentEng London 2026 recordings "
                "from /london-2026/videos (the welcome video, then talks marked "
                "recording-coming-soon) and the Harness Engineering San Francisco full-event "
                "recording, with YouTube IDs when published and /gallery/<slug> links. One item "
                "by slug: talk with session_id set to the slug. A2A talks are added only with "
                "include_a2a, listed last and labelled AI-generated. Model-free.",
                tags=["gallery", "videos", "recordings", "london-2026", "san-francisco"],
                examples=[
                    '{"operation":"gallery"}',
                    '{"operation":"gallery","city":"London"}',
                    '{"operation":"talk","session_id":"london-2026-welcome"}',
                ],
            ),
            AgentSkill(
                id="agenteng-talks",
                name="Programme talks",
                description="Every programme talk with its full abstract (talks; optional city, "
                "event_id, topic, query and speaker_id): AgentEng London 2026, Code Engineering "
                "San Francisco (27 October 2026, linked to /san-francisco) and the Harness "
                "Engineering San Francisco sessions, each with its recording status. One talk: "
                "talk with session_id set to a slug or session ID. Never lists A2A talks; use "
                "gallery for videos. Model-free.",
                tags=["talks", "abstracts", "london-2026", "code-engineering", "san-francisco"],
                examples=[
                    '{"operation":"talks","city":"San Francisco"}',
                    '{"operation":"talks","event_id":"agenteng-london-2026","topic":"Memory"}',
                    '{"operation":"talk","session_id":"london-2026-say-less-grade-harder"}',
                ],
            ),
            AgentSkill(
                id="agenteng-a2a-talks",
                name="Agent-to-Agent (A2A) Talks",
                description="The published Agent-to-Agent (A2A) Talks page (a2a-talks; optional "
                "topic filters by discipline tag such as memory or security): short AI-generated "
                "videos of two AI agents discussing one engineering discipline, with titles, "
                "YouTube links, durations and tags. These videos are produced by the Agent "
                "Engineering team using AI. They are separate from the conference programme and "
                "are not created, reviewed or endorsed by our speakers. They are never returned as "
                "speakers, talks or sessions, and gallery lists them only with include_a2a, last. Model-free.",
                tags=["a2a-talks", "agent-to-agent", "videos", "ai-generated"],
                examples=[
                    '{"operation":"a2a-talks"}',
                    '{"operation":"a2a-talks","topic":"memory"}',
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
        ],
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
