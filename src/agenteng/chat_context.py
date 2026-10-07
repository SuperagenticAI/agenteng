"""Small, reviewed public context for chat and its model-free fallback.

Protocol summaries are bundled paraphrases of the linked official introductions.
No runtime web, private catalogue, or model is needed to answer these basics.
"""

import re
from zoneinfo import ZoneInfo

from .models import Request, Source

PROTOCOLS = {
    "cli": Source(
        id="protocol-cli",
        url="https://docs.agentengineering.world/COMMANDS/",
        text="CLI means command-line interface. The AgentEng CLI lets you explore public events, speakers, agendas and agent engineering tools from your terminal.",
    ),
    "mcp": Source(
        id="protocol-mcp",
        url="https://modelcontextprotocol.io/docs/getting-started/intro",
        text="MCP (Model Context Protocol) connects AI applications to tools, data sources and external systems through a shared client/server interface.",
    ),
    "a2a": Source(
        id="protocol-a2a",
        url="https://a2a-protocol.org/latest/topics/what-is-a2a/",
        text="A2A (Agent2Agent) is a protocol for agents to discover each other, exchange messages and collaborate across frameworks or vendors. MCP connects an agent to tools; A2A connects agents to other agents.",
    ),
    "acp": Source(
        id="protocol-acp",
        url="https://agentclientprotocol.com/get-started/introduction",
        text="ACP (Agent Client Protocol) standardizes communication between coding agents and clients such as editors. A client can use the same interface to work with different compatible coding agents.",
    ),
}

TOOLING = Source(
    id="agenteng-tooling",
    url="https://docs.agentengineering.world/INTEGRATIONS/",
    text="AgentEng combines Agent Engineering events with open-source agent infrastructure: a CLI, MCP tools, an A2A agent and optional ACP coding-agent integration. Install it with curl -fsSL https://agentengineering.world/install.sh | sh. Run agenteng connect cursor, agenteng connect codex or agenteng connect claude-code for MCP setup.",
)


def attendance_question(question):
    """FAQ is an attendance resource, never a general chat search."""
    return bool(
        re.search(
            r"\b(?:faq|attend(?:ing|ance)?|tickets?|refunds?|invoices?|transfer|approval|"
            r"approved|registration|register|accessible|accessibility|wheelchair|dietary|"
            r"food|lunch|drinks?|catering|cancel(?:led|lation)?|conduct|dress|seats?)\b",
            question,
            re.I,
        )
    )


def focused_search(service, question, limit, *, allow_faq=None):
    """Ignore conversational filler and require meaningful overlap with a source."""
    from .service import terms

    if allow_faq is None:
        allow_faq = attendance_question(question)
    filler = {
        "you",
        "your",
        "yours",
        "we",
        "our",
        "they",
        "their",
        "it",
        "its",
        "do",
        "have",
        "has",
        "to",
        "be",
        "in",
        "on",
        "at",
        "from",
        "an",
        "as",
        "by",
        "am",
        "my",
        "would",
        "could",
        "should",
        "will",
        "want",
        "need",
        "know",
        "help",
        "explain",
        "understand",
        "give",
        "get",
        "some",
        "any",
        "more",
        "there",
    }
    wanted = terms(question) - filler
    minimum = max(1, len(wanted) // 2 + 1)
    ranked = sorted(
        (
            (len(wanted & terms(source.text)), source)
            for source in service.catalogue.sources
            if allow_faq or source.kind not in {"faq", "conduct", "tickets"}
        ),
        key=lambda item: (-item[0], item[1].id),
    )
    matches = [source for score, source in ranked if score >= minimum][: min(limit, 2)]
    if not wanted or not matches:
        return service.result(
            "I don't have enough public information to answer that yet. Ask me about AgentEng, the events, or agent engineering tools, or add a little more detail.",
            status="not_found",
        )
    return service.result("\n\n".join(source.text[:900] for source in matches)).model_copy(
        update={"sources": matches}
    )


def resolved_question(request):
    question = request.query
    if re.fullmatch(
        r"\s*(?:tell me more|more|go on|explain more|can you elaborate|please elaborate)[.!?\s]*",
        question,
        re.I,
    ):
        previous = next(
            (turn.content for turn in reversed(request.history) if turn.role == "user"), None
        )
        if previous:
            return previous
    return question


def published_talk_answer(service, request):
    """Answer topical speaker/session questions from the published programme."""
    from .service import terms

    question = resolved_question(request)
    plain = question.casefold()
    if not re.search(r"\b(?:speaking|talking|presenting|speakers?|talks?|sessions?)\b", plain):
        return None
    if re.search(r"\b(?:tools?|libraries|frameworks|submit|proposal|propose)\b", plain):
        return None
    if re.search(r"\bfrom\b", plain) and not re.search(r"\b(?:about|on|covering)\b", plain):
        # Company/affiliation filters belong to the existing speaker lookup.
        return None
    city = request.city or next(
        (e.city for e in service.catalogue.events if e.city.casefold() in plain), None
    )
    if not city and re.search(r"\bsf\b", plain):
        city = "San Francisco"
    filler = {
        "who",
        "us",
        "you",
        "they",
        "will",
        "be",
        "do",
        "does",
        "has",
        "have",
        "talking",
        "speaking",
        "presenting",
        "speaker",
        "speakers",
        "talk",
        "talks",
        "session",
        "sessions",
        "give",
        "giving",
        "cover",
        "covering",
        "covers",
        "on",
        "in",
        "at",
        "to",
        "from",
        "by",
        "time",
        "start",
        "starts",
        "scheduled",
        "show",
        "list",
        "find",
        "any",
        "there",
        "engineering",
        "agenteng",
        "conference",
        "next",
        "upcoming",
        "past",
    }
    wanted = terms(question) - filler - terms(city or "")
    if not wanted:
        return None
    scoped = service.matching_events(request.model_copy(update={"city": city}))
    events = {
        e.id: e
        for e in scoped
        if service.state(e) != "cancelled"
        and (request.event_id or request.past or service.state(e) in {"upcoming", "ongoing"})
    }
    speakers = service.speaker_map()
    matches = []
    for session in service.catalogue.sessions:
        speaker = speakers.get(session.speaker_id)
        if session.event_id not in events or not speaker:
            continue
        title = terms(" ".join([session.title, *session.topics, speaker.name]))
        evidence = title | terms(speaker.abstract or "") | terms(" ".join(speaker.disciplines))
        if wanted <= evidence:
            matches.append((len(wanted & title), session, speaker))
    if not matches:
        return service.result(
            "No published talk matches that topic in the requested events. Try another topic or city.",
            [],
            status="not_found",
        )
    # Exact title/topic matches take precedence over incidental abstract mentions.
    best = max(score for score, _, _ in matches)
    matches = [item for item in matches if item[0] == best][: request.limit]
    answers, data, source_ids = [], [], []
    for _, session, speaker in matches:
        event = events[session.event_id]
        answer = f"{speaker.name}{' from ' + speaker.company if speaker.company else ''} is presenting “{session.title}” at {event.title}."
        if session.start:
            start = session.start.astimezone(ZoneInfo(event.timezone))
            end = session.end.astimezone(ZoneInfo(event.timezone)) if session.end else None
            hours = f"{start:%H:%M}" + (f"–{end:%H:%M}" if end else "")
            answer += f" Scheduled for {start:%d %B %Y}, {hours} ({event.timezone})."
        else:
            answer += " The session time has not been published yet."
        answers.append(answer)
        talk = service.talk_payload(session)
        data.append(
            {**speaker.model_dump(mode="json"), "talk": talk}
            if re.search(r"\b(?:who|speakers?)\b", plain)
            else talk
        )
        source_ids.extend([*session.source_ids, *speaker.source_ids, *event.source_ids])
    return service.result("\n\n".join(answers), data, source_ids)


def chat_fallback(service, request):
    question = resolved_question(request)
    plain = question.casefold().replace("’", "'").strip(" .!?\n\t")
    if re.fullmatch(
        r"(?:hi|hello|hey)(?: there| agenteng)?(?:[,!] ?)?(?: how are you)?", plain
    ) or plain in {
        "how are you",
        "how are you doing",
        "how's it going",
        "what's up",
        "good morning",
        "good afternoon",
        "good evening",
    }:
        return service.result(
            "Hey! I'm ready to help. Want to explore AgentEng, the events, or building with MCP, A2A and ACP?"
            if "how" in plain or "what's up" in plain
            else "Hi! I'm AgentEng. Ask me about the events, speakers, or agent engineering tools. What would you like to explore?"
        )
    if plain in {"thanks", "thank you", "thank you very much", "great", "cool", "ok", "okay"}:
        return service.result("You're welcome! What would you like to explore next?")
    if re.fullmatch(
        r"(?:who are you|what (?:are you|can you do)|help|(?:what(?:'s| is) |tell me about )agenteng)",
        plain,
    ):
        return service.result(
            "I'm AgentEng, your guide to Agent Engineering events and open-source agent infrastructure. Explore speakers, talks and agendas, or build with our CLI, MCP, A2A and ACP tooling. What are you working on?"
        ).model_copy(update={"sources": [TOOLING]})
    if re.fullmatch(r"(?:what(?:'s| is) |explain |tell me about )agent engineering", plain):
        about = service.catalogue.about
        if about and about.definition:
            return service.result(about.definition, source_ids=about.source_ids)
    if re.search(r"\b(?:install|installation|connect|setup|set up)\b", plain) and re.search(
        r"\b(?:agenteng|mcp|a2a|acp)\b", plain
    ):
        origin = service.settings.public_url
        return service.result(
            TOOLING.text
            + f" The public A2A endpoint is {origin} and the remote MCP endpoint is {origin}/mcp/."
        ).model_copy(update={"sources": [TOOLING]})
    protocols = list(dict.fromkeys(re.findall(r"\b(?:mcp|a2a|acp|cli)\b", plain)))
    definition = re.search(
        r"\b(?:what(?:'s| is| are)|explain|mean|difference|compare|tell me about|understand|how .*works?)\b",
        question,
        re.I,
    )
    event_or_tools = re.search(
        r"\b(?:speakers?|talks?|agenda|schedule|tickets?|price|tools?|libraries|frameworks|conference)\b",
        question,
        re.I,
    )
    if (
        protocols
        and not event_or_tools
        and (definition or question.strip().casefold() in PROTOCOLS)
    ):
        sources = [PROTOCOLS[name] for name in protocols]
        return service.result("\n\n".join(source.text for source in sources)).model_copy(
            update={"sources": sources}
        )
    result = service.lookup(Request(operation="ask", query=question, limit=request.limit))
    if result.answer.startswith(("Published source excerpts", "No published sources")):
        return focused_search(service, question, request.limit)
    return result


def cited_data(candidates, source_ids):
    """Choose cards from the lookup actually cited, not an unrelated last tool call."""
    chosen = set(source_ids)
    matching = [
        (len(chosen & ids), index, data)
        for index, (ids, data) in enumerate(candidates)
        if chosen & ids
    ]
    return max(matching, key=lambda item: item[:2])[2] if matching else {}
