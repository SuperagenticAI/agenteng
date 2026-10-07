"""One catalogue service used unchanged by CLI, MCP and A2A."""

from __future__ import annotations

import asyncio
import hmac
import re
import threading
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .calendar import calendar
from .catalogue import load_catalogue
from .config import Settings
from .models import Catalogue, Event, Request, Result, Session, Speaker
from .participation import CITIES
from .tool_directory import TOOL_OPERATIONS, ToolDirectory, load_tool_directory


def terms(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "what",
        "when",
        "where",
        "which",
        "are",
        "can",
        "about",
        "how",
        "does",
        "this",
        "that",
        "please",
        "tell",
        "me",
        "is",
        "a",
        "of",
    }
    return {x for x in re.findall(r"[\w]+", text.casefold()) if x not in stop and len(x) > 1}


class Service:
    def __init__(
        self,
        settings: Settings | None = None,
        catalogue: Catalogue | None = None,
        *,
        clock=None,
        provider=None,
        tool_directory: ToolDirectory | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.catalogue = catalogue or load_catalogue(self.settings.catalogue_path)
        if any(event.city not in CITIES for event in self.catalogue.events):
            raise ValueError("AgentEng supports only London and San Francisco catalogues")
        self.clock = clock or (lambda: datetime.now(UTC))
        self.provider = provider
        self.tool_directory = tool_directory or load_tool_directory()
        self.sources = {s.id: s for s in self.catalogue.sources}
        self.events = {e.id: e for e in self.catalogue.events}
        # Optional inference is serialized per process; it is operator-only.
        self._model_slot = threading.Lock()
        self._chat_runtime = None

    def authorized(self, token: str | None) -> bool:
        expected = self.settings.operator_token
        return bool(expected and token and hmac.compare_digest(expected.encode(), token.encode()))

    def result(self, answer: str, data=None, source_ids=(), **kwargs) -> Result:
        now = self.clock()
        return Result(
            answer=answer,
            data={} if data is None else data,
            sources=[self.sources[s] for s in dict.fromkeys(source_ids)],
            catalogue_version=self.catalogue.version,
            evaluated_at=now,
            published_at=self.catalogue.published_at,
            stale=(now - self.catalogue.published_at).total_seconds()
            > self.settings.max_age_hours * 3600,
            **kwargs,
        )

    def state(self, event: Event) -> str:
        if event.cancelled:
            return "cancelled"
        local = self.clock().astimezone(ZoneInfo(event.timezone))
        if event.date_precision == "month":
            # Do not label an event past/upcoming within its unknown event month.
            month = local.strftime("%Y-%m")
            return "past" if event.date < month else "upcoming" if event.date > month else "unknown"
        if event.end:
            return (
                "past"
                if local >= event.end
                else "ongoing"
                if event.start and local >= event.start
                else "upcoming"
            )
        if event.start and local < event.start:
            return "upcoming"
        return (
            "past"
            if event.date < local.date().isoformat()
            else "unknown"
            if event.date == local.date().isoformat()
            else "upcoming"
        )

    def event_data(self, event):
        return {**event.model_dump(mode="json"), "state": self.state(event)}

    def matching_events(self, request):
        return [
            e
            for e in self.catalogue.events
            if (not request.event_id or e.id == request.event_id)
            and (not request.city or e.city.casefold() == request.city.casefold())
            and (not request.upcoming or self.state(e) == "upcoming")
            and (not request.past or self.state(e) == "past")
        ]

    def speaker_map(self) -> dict[str, Speaker]:
        return {s.id: s for s in self.catalogue.speakers}

    def session_map(self) -> dict[str, Session]:
        return {s.id: s for s in self.catalogue.sessions}

    def talk_payload(self, session: Session) -> dict:
        speaker = self.speaker_map().get(session.speaker_id) if session.speaker_id else None
        payload = session.model_dump(mode="json")
        if speaker:
            payload.update(
                {
                    "speaker_name": speaker.name,
                    "speaker_role": speaker.role,
                    "speaker_company": speaker.company,
                    "abstract": speaker.abstract,
                    "talk_title": speaker.talk_title or session.title,
                    "disciplines": list(speaker.disciplines),
                    "speaker": speaker.model_dump(mode="json"),
                }
            )
        else:
            payload.setdefault("abstract", None)
            payload.setdefault("talk_title", session.title)
            payload.setdefault("disciplines", [])
        return payload

    def default_live_event_id(self, request: Request) -> str | None:
        if request.event_id:
            return request.event_id
        scoped = self.matching_events(request)
        live = [e for e in scoped if self.state(e) in {"upcoming", "ongoing"} and e.start and e.end]
        if len(live) == 1:
            return live[0].id
        day = [
            e
            for e in scoped
            if e.date_precision == "day" and e.start and e.end and self.state(e) != "cancelled"
        ]
        if len(day) == 1:
            return day[0].id
        london = next((e for e in day if e.id == "agenteng-london-2026"), None)
        return london.id if london else (day[0].id if day else None)

    def lookup(self, request: Request) -> Result:
        if request.operation == "chat":
            return self.lookup(Request(operation="ask", query=request.query, limit=request.limit))
        if request.operation in TOOL_OPERATIONS:
            return self.tool_directory.lookup(request, self.clock(), self.settings.max_age_hours)
        if request.event_id and request.event_id not in self.events:
            return self.result(
                "Unknown event_id. Use events to list published event IDs.", status="not_found"
            )
        if request.operation == "discover":
            from .discovery import discovery, featured_events

            return self.result(
                "Agent Engineering HQ runs AgentEng conferences and technical events in London and San Francisco.",
                discovery(self, request.city),
                (["hq"] if "hq" in self.sources else [])
                + [
                    i
                    for e in featured_events(self)
                    if not request.city or e.city.casefold() == request.city.casefold()
                    for i in e.source_ids
                ],
            )
        if request.operation == "participate":
            contact = self.sources.get("contact")
            address = (
                re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", contact.text) if contact else None
            )
            if not address:
                return self.result(
                    "No public organizer contact is available in this catalogue.",
                    status="unavailable",
                )
            email = address.group()
            return self.result(
                f"To discuss a talk or event idea, contact the organizer yourself at {email}. "
                "Ideas are for possible consideration; no review deadline, response, acceptance "
                "or event is guaranteed. AgentEng provides public information only and accepts no "
                "submissions. London 2026 has an invited programme and no public CFP.",
                {
                    "organizer_email": email,
                    "contact_url": "mailto:" + email,
                    "automated_submission_available": False,
                    "private_intake_enabled": False,
                    "participant_credential_required": False,
                    "organizer": "Agent Engineering HQ",
                    "cities": ["London", "San Francisco"],
                    "offline_drafting_available": False,
                    "current_event_policy": "London 2026 has an invited programme and no public CFP. "
                    "No San Francisco public CFP is announced in this snapshot. "
                    "Future-event ideas are for possible consideration.",
                    "privacy_guidance": "Share only the information needed for a reply. Keep private "
                    "proposals and contact details out of public GitHub issues.",
                },
                [contact.id],
            )
        if request.operation == "ask":
            from .chat_context import focused_search, published_talk_answer

            if terms(request.query) & {"travel", "accommodation", "visa", "visas"}:
                return focused_search(self, request.query, request.limit, allow_faq=True)

            talk_answer = published_talk_answer(self, request)
            if talk_answer is not None:
                return talk_answer
            query_terms = terms(request.query)
            if query_terms & {"doors", "arrival", "arrive", "checkin"}:
                city = request.city or next(
                    (city for city in CITIES if city.casefold() in request.query.casefold()), None
                )
                events = self.matching_events(request.model_copy(update={"city": city}))
                events = [e for e in events if self.state(e) in {"upcoming", "ongoing"}]
                if len(events) == 1:
                    event = events[0]
                    opening = next(
                        (
                            s
                            for s in self.catalogue.sessions
                            if s.event_id == event.id and s.kind == "open" and s.start
                        ),
                        None,
                    )
                    if opening:
                        local = opening.start.astimezone(ZoneInfo(event.timezone))
                        return self.result(
                            f"{opening.title}: {local:%H:%M} on {local:%d %B %Y} ({event.timezone}), at {event.venue}.",
                            self.talk_payload(opening),
                            opening.source_ids,
                        )
            if (
                not request.event_id
                and not request.city
                and query_terms & {"tools", "tool", "frameworks", "libraries"}
                and not query_terms
                & {
                    "proposal",
                    "proposals",
                    "submit",
                    "participate",
                    "speakers",
                    "speaker",
                    "speaking",
                    "tickets",
                    "ticket",
                    "agenda",
                    "events",
                    "conference",
                }
            ):
                from .tool_directory import DISCIPLINES

                aliases = {"evaluation": "eval", "coding": "code", **{d: d for d in DISCIPLINES}}
                discipline = next(
                    (aliases[word] for word in sorted(query_terms) if word in aliases), None
                )
                filler = {
                    "list",
                    "find",
                    "show",
                    "suggest",
                    "recommend",
                    "popular",
                    "best",
                    "top",
                    "tools",
                    "tool",
                    "frameworks",
                    "libraries",
                    "engineering",
                    "agent",
                    "agents",
                    "agenteng",
                    "available",
                    "some",
                    "all",
                    "use",
                    "using",
                    *aliases,
                }
                routed = Request(
                    operation="tools",
                    discipline=discipline,
                    query=" ".join(sorted(query_terms - filler)),
                    limit=request.limit,
                )
                return self.lookup(routed)
            if (
                re.search(r"\b(agent\s*[- ]?eng(?:ineering)?|agenteng)\b", request.query.casefold())
                and not (
                    query_terms
                    & {
                        "tickets",
                        "ticket",
                        "price",
                        "prices",
                        "agenda",
                        "schedule",
                        "speakers",
                        "speaker",
                        "speaking",
                        "recordings",
                        "proposal",
                        "propose",
                        "submit",
                        "participate",
                    }
                )
                and not request.event_id
            ):
                city = request.city or next(
                    (city for city in CITIES if city.casefold() in request.query.casefold()), None
                )
                if not city and re.search(r"\bsf\b", request.query.casefold()):
                    city = "San Francisco"
                return self.lookup(
                    request.model_copy(
                        update={"operation": "discover", "engine": "lookup", "city": city}
                    )
                )
            if query_terms & {
                "participate",
                "proposal",
                "proposals",
                "propose",
                "contribute",
            }:
                return self.lookup(
                    request.model_copy(update={"operation": "participate", "engine": "lookup"})
                )
            city = request.city or next(
                (
                    e.city
                    for e in self.catalogue.events
                    if e.city.casefold() in request.query.casefold()
                ),
                None,
            )
            if not city and re.search(r"\bsf\b", request.query.casefold()):
                city = "San Francisco"
            scope = self.matching_events(request.model_copy(update={"city": city}))
            current = [e for e in scope if self.state(e) in {"upcoming", "ongoing"}]
            target = request.event_id or (current[0].id if len(current) == 1 else None)
            operation = None
            if query_terms & {
                "ticket",
                "tickets",
                "price",
                "prices",
                "cost",
                "register",
                "registration",
            }:
                operation = "tickets"
            elif query_terms & {"agenda", "schedule", "programme"}:
                operation = "agenda"
            elif query_terms & {"speakers", "speaker", "speaking", "lineup"}:
                operation = "speakers"
            elif query_terms & {"recording", "recordings", "videos"}:
                operation = "recordings"
            elif query_terms & {"when", "where", "date", "dates", "venue", "events", "conference"}:
                # 'when'/'where' are stop words in search but valid intent markers.
                operation = "events"
            elif re.search(r"\b(when|where)\b", request.query.casefold()):
                operation = "events"
            if operation:
                if operation in {"tickets", "agenda"} and not target:
                    return self.result(
                        "Choose an event_id to read its ticket terms or agenda.",
                        [self.event_data(e) for e in current],
                        [i for e in current for i in e.source_ids],
                        status="unavailable",
                    )
                routed = request.model_copy(
                    update={
                        "operation": operation,
                        "engine": "lookup",
                        "event_id": target
                        if operation in {"tickets", "agenda"}
                        else request.event_id,
                        "city": city,
                        "upcoming": bool(query_terms & {"next", "upcoming"}),
                    }
                )
                if operation == "speakers":
                    intent_words = {
                        "who",
                        "speakers",
                        "speaker",
                        "speaking",
                        "lineup",
                        "show",
                        "list",
                        "in",
                        "at",
                        "on",
                        "from",
                        "agenteng",
                        "agent",
                        "engineering",
                        "conference",
                    }
                    routed = routed.model_copy(
                        update={
                            "query": " ".join(
                                sorted(query_terms - intent_words - terms(city or ""))
                            )
                        }
                    )
                return self.lookup(routed)
        events = self.matching_events(request)
        ids = {e.id for e in events}
        if request.operation in {"events", "event"}:
            rows = sorted(events, key=lambda e: (e.date, e.id))[: request.limit]
            return self.result(
                f"{len(rows)} published event(s).",
                [self.event_data(e) for e in rows],
                [s for e in rows for s in e.source_ids],
                status="ok" if rows else "not_found",
            )
        if request.operation == "speakers":
            rows = [s for s in self.catalogue.speakers if ids.intersection(s.event_ids)]
            if request.speaker_id:
                rows = [s for s in rows if s.id == request.speaker_id]
            wanted = terms(request.query)
            if wanted:
                rows = [
                    s
                    for s in rows
                    if wanted
                    & terms(
                        " ".join(
                            [
                                s.id,
                                s.name,
                                s.role,
                                s.company,
                                s.note or "",
                                s.talk_title or "",
                                s.abstract or "",
                                " ".join(s.disciplines),
                            ]
                        )
                    )
                ]
            rows = rows[: request.limit]
            return self.result(
                f"{len(rows)} published speaker(s).",
                [s.model_dump(mode="json") for s in rows],
                [i for s in rows for i in s.source_ids],
                status="ok" if rows else "not_found",
            )
        if request.operation == "speaker":
            speaker = self.speaker_map().get(request.speaker_id or "")
            if not speaker:
                return self.result(
                    "Unknown speaker_id. Use speakers to list published speaker IDs.",
                    status="not_found",
                )
            if ids and not ids.intersection(speaker.event_ids):
                return self.result(
                    "Speaker is not linked to the requested event filters.",
                    status="not_found",
                )
            talk = next(
                (
                    self.talk_payload(s)
                    for s in self.catalogue.sessions
                    if s.speaker_id == speaker.id and s.kind == "talk"
                ),
                None,
            )
            data = speaker.model_dump(mode="json")
            data["talk"] = talk
            return self.result(
                f"{speaker.name}: {speaker.talk_title or 'talk not announced'}.",
                data,
                speaker.source_ids,
            )
        if request.operation in {"talks", "talk"}:
            rows = [
                s
                for s in self.catalogue.sessions
                if s.event_id in ids and (s.kind == "talk" or s.speaker_id)
            ]
            if request.session_id:
                rows = [s for s in rows if s.id == request.session_id]
            if request.speaker_id:
                rows = [s for s in rows if s.speaker_id == request.speaker_id]
            wanted = terms(request.query or request.topic or "")
            if wanted:
                rows = [
                    s
                    for s in rows
                    if wanted
                    & terms(
                        " ".join(
                            [
                                s.title,
                                " ".join(s.topics),
                                " ".join(self.sources[i].text for i in s.source_ids),
                                (
                                    self.speaker_map()[s.speaker_id].abstract
                                    if s.speaker_id and s.speaker_id in self.speaker_map()
                                    else ""
                                )
                                or "",
                                (
                                    self.speaker_map()[s.speaker_id].name
                                    if s.speaker_id and s.speaker_id in self.speaker_map()
                                    else ""
                                ),
                            ]
                        )
                    )
                ]
            if request.operation == "talk":
                if not rows:
                    return self.result("No published talk matched.", status="not_found")
                session = rows[0]
                return self.result(
                    f"Talk: {session.title}.",
                    self.talk_payload(session),
                    session.source_ids,
                )
            rows = rows[: request.limit]
            return self.result(
                f"{len(rows)} published talk(s).",
                [self.talk_payload(s) for s in rows],
                [i for s in rows for i in s.source_ids],
                status="ok" if rows else "not_found",
            )
        if request.operation == "faq":
            rows = list(self.catalogue.faqs)
            if request.event_id:
                rows = [f for f in rows if f.event_id in {None, request.event_id}]
            wanted = terms(request.query)
            if wanted:
                rows = [f for f in rows if wanted & terms(f.question + " " + f.answer)]
            rows = rows[: request.limit]
            return self.result(
                f"{len(rows)} FAQ entr{'y' if len(rows) == 1 else 'ies'}.",
                [f.model_dump(mode="json") for f in rows],
                [i for f in rows for i in f.source_ids],
                status="ok" if rows else "not_found",
            )
        if request.operation == "venue":
            event = self.events.get(request.event_id or "")
            if not event:
                return self.result("Unknown event_id.", status="not_found")
            accessibility = next(
                (
                    f
                    for f in self.catalogue.faqs
                    if "accessible" in f.question.casefold() and f.event_id in {None, event.id}
                ),
                None,
            )
            data = {
                "event_id": event.id,
                "venue": event.venue,
                "city": event.city,
                "timezone": event.timezone,
                "track": event.track or "single",
                "venue_tour_url": str(event.venue_tour_url) if event.venue_tour_url else None,
                "accessibility": accessibility.answer if accessibility else None,
                "start": event.start.isoformat() if event.start else None,
                "end": event.end.isoformat() if event.end else None,
            }
            source_ids = list(event.source_ids)
            if accessibility:
                source_ids.extend(accessibility.source_ids)
            return self.result(
                f"Venue for {event.title}: {event.venue}.",
                data,
                source_ids,
            )
        if request.operation == "sponsors":
            sponsors = list(self.catalogue.sponsors)
            if request.city:
                sponsors = [s for s in sponsors if s.city.casefold() == request.city.casefold()]
            contact = self.sources.get("sponsor-contact") or self.sources.get("contact")
            data = {
                "sponsors": [s.model_dump(mode="json") for s in sponsors],
                "support_options": [
                    s.model_dump(mode="json") for s in self.catalogue.support_options
                ],
                "sponsor_email": None,
                "note": (
                    "London 2026 lists practical support options rather than founding or title packages. "
                    "San Francisco events list published partners."
                ),
            }
            if contact:
                match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", contact.text)
                if match:
                    data["sponsor_email"] = match.group()
            source_ids = [
                s.id for s in self.catalogue.sources if s.kind in {"sponsor", "sponsorship"}
            ]
            return self.result(
                f"{len(sponsors)} published sponsor(s); {len(self.catalogue.support_options)} support option(s).",
                data,
                source_ids or ([contact.id] if contact else []),
                status="ok" if sponsors or self.catalogue.support_options else "not_found",
            )
        if request.operation == "conduct":
            conduct = self.sources.get("code-of-conduct")
            faq = next(
                (f for f in self.catalogue.faqs if "code of conduct" in f.question.casefold()),
                None,
            )
            if not conduct and not faq:
                return self.result(
                    "No published code of conduct summary in this catalogue.",
                    status="not_found",
                )
            data = {
                "url": "https://agentengineering.world/code-of-conduct",
                "report_email": "conduct@super-agentic.ai",
                "summary": (conduct.text if conduct else faq.answer),
                "terms_url": "https://agentengineering.world/terms",
            }
            return self.result(
                "Code of conduct applies to attendees, speakers, partners, volunteers and organisers.",
                data,
                [conduct.id] if conduct else faq.source_ids,
            )
        if request.operation == "themes":
            rows = list(self.catalogue.themes)[: request.limit]
            source_ids = [s.id for s in self.catalogue.sources if s.kind == "theme"]
            return self.result(
                f"{len(rows)} program theme(s).",
                [t.model_dump(mode="json") for t in rows],
                source_ids,
                status="ok" if rows else "not_found",
            )
        if request.operation in {"about", "hq", "live", "bingo"}:
            from . import screens

            return getattr(screens, request.operation)(self, request)
        if request.operation in {"now", "next"}:
            from .screens import local_now

            event_id = self.default_live_event_id(request)
            if not event_id:
                return self.result(
                    "Choose an event_id with a published timed agenda.",
                    status="unavailable",
                )
            event = self.events[event_id]
            if event.cancelled:
                return self.result(
                    "This event is cancelled; no scheduled sessions are running.",
                    {"event_id": event_id, "session": None, "state": "cancelled"},
                    event.source_ids,
                    status="unavailable",
                )
            now = local_now(self, request, event.timezone)
            timed = [
                s for s in self.catalogue.sessions if s.event_id == event_id and s.start and s.end
            ]
            timed.sort(key=lambda s: s.start)
            current = next((s for s in timed if s.start <= now < s.end), None)
            upcoming = next((s for s in timed if s.start > now), None)
            if request.operation == "now":
                if current:
                    return self.result(
                        f"Now: {current.title}.",
                        {
                            "event_id": event_id,
                            "as_of": now.isoformat(),
                            "session": self.talk_payload(current),
                        },
                        current.source_ids,
                    )
                return self.result(
                    "Nothing is on right now in the published agenda.",
                    {
                        "event_id": event_id,
                        "as_of": now.isoformat(),
                        "session": None,
                        "next": self.talk_payload(upcoming) if upcoming else None,
                    },
                    event.source_ids,
                    status="not_found",
                )
            if upcoming:
                return self.result(
                    f"Next: {upcoming.title}.",
                    {
                        "event_id": event_id,
                        "as_of": now.isoformat(),
                        "session": self.talk_payload(upcoming),
                    },
                    upcoming.source_ids,
                )
            return self.result(
                "No later sessions remain in the published agenda.",
                {"event_id": event_id, "as_of": now.isoformat(), "session": None},
                event.source_ids,
                status="not_found",
            )
        if request.operation == "agenda":
            rows = [s for s in self.catalogue.sessions if s.event_id in ids]
            if request.session_id:
                rows = [s for s in rows if s.id == request.session_id]
            wanted = terms(request.topic or "")
            if wanted:
                rows = [
                    s
                    for s in rows
                    if wanted
                    & terms(
                        s.title
                        + " "
                        + " ".join(s.topics)
                        + " "
                        + " ".join(self.sources[i].text for i in s.source_ids)
                    )
                ]
            rows = rows[: request.limit]
            artifact = None
            if request.format == "ics":
                event = self.events[request.event_id]
                timed = [s for s in rows if s.start and s.end]
                if not timed:
                    return self.result(
                        "No selected sessions have published start and end times; calendar export unavailable.",
                        status="unavailable",
                    )
                artifact = calendar(event, timed, self.clock())
            return self.result(
                f"{len(rows)} agenda entry/entries matched. This is the published agenda; attendance is subject to registration.",
                [s.model_dump(mode="json") for s in rows],
                [i for s in rows for i in s.source_ids],
                artifact=artifact,
                status="ok" if rows else "not_found",
            )
        if request.operation == "tickets":
            if not events:
                return self.result("No event matches the filters.", status="not_found")
            event = events[0]
            now = self.clock()
            current = [
                o.model_dump(mode="json")
                for o in event.offers
                if o.valid_from <= now
                and (o.valid_until is None or now < o.valid_until)
                and not o.sold_out
                and self.state(event) not in {"past", "cancelled"}
            ]
            return self.result(
                "Published price window only. Availability and approval must be confirmed on the registration page.",
                {
                    "event_id": event.id,
                    "current_offers": current,
                    "published_offers": [o.model_dump(mode="json") for o in event.offers],
                    "registration_url": str(event.registration_url)
                    if event.registration_url
                    else None,
                    "state": self.state(event),
                    "live_availability_verified": False,
                },
                event.source_ids,
            )
        if request.operation == "recordings":
            rows = [e for e in events if e.recording_url][: request.limit]
            return self.result(
                f"{len(rows)} published recording link(s).",
                [{"event_id": e.id, "title": e.title, "url": str(e.recording_url)} for e in rows],
                [s for e in rows for s in e.source_ids],
                status="ok" if rows else "not_found",
            )
        # Search/ask returns literal, attributed excerpts. It never paraphrases with a model.
        wanted = terms(request.query)
        candidates = [
            s
            for s in self.catalogue.sources
            if (
                s.event_id in ids
                or (not request.event_id and not request.city and s.event_id is None)
            )
        ]
        scored = sorted(
            [(len(wanted & terms(s.text)), s) for s in candidates],
            key=lambda item: (-item[0], item[1].id),
        )
        rows = [s for score, s in scored if score > 0][: request.limit]
        answer = (
            "Published source excerpts matched your query."
            if rows
            else "No published sources matched. Try events, agenda, tickets or a more specific query."
        )
        return self.result(
            answer,
            [{"source_id": s.id, "excerpt": s.text, "url": str(s.url)} for s in rows],
            [s.id for s in rows],
            status="ok" if rows else "not_found",
        )

    async def execute(self, request: Request, *, token: str | None = None) -> Result:
        if request.operation == "chat":
            from .public_chat import PublicChat

            if self._chat_runtime is None:
                self._chat_runtime = PublicChat(self)
            return await self._chat_runtime.execute(request)
        if request.engine in {"lookup", "auto"}:
            # auto deliberately stays model-free in this release.
            return self.lookup(request)
        enabled = (
            self.settings.enable_rlm if request.engine == "rlm" else self.settings.enable_standard
        )
        if not enabled:
            return self.result(
                f"{request.engine} engine is disabled by the operator.", status="unavailable"
            )
        if not self.authorized(token):
            return self.result(
                "Optional model engines require the operator credential.", status="unavailable"
            )
        if not self.provider and not (self.settings.model and self.settings.model_api_key):
            return self.result("Optional model provider is not configured.", status="unavailable")
        evidence = self.lookup(request.model_copy(update={"engine": "lookup"}))
        if not evidence.sources:
            return evidence
        if not self._model_slot.acquire(blocking=False):
            return self.result(
                "Optional inference is busy; retry later or use lookup.", status="unavailable"
            )
        cancelled = threading.Event()

        def run():
            # Lock remains held if the client cancels while a provider call is in flight.
            try:
                from .engines import run_engine

                return run_engine(
                    request,
                    evidence.sources,
                    self.settings,
                    self.provider,
                    cancelled,
                    snapshot={
                        "evaluated_at": evidence.evaluated_at.isoformat(),
                        "published_at": evidence.published_at.isoformat(),
                        "stale": evidence.stale,
                    },
                )
            finally:
                self._model_slot.release()

        try:
            future = asyncio.get_running_loop().run_in_executor(None, run)
            # Shield the queued worker too: cancellation must not strand its acquired slot.
            future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
            output = await asyncio.wait_for(asyncio.shield(future), self.settings.request_timeout)
            return self.result(
                output["answer"],
                source_ids=output["source_ids"],
                engine=request.engine,
                usage=output["usage"],
            )
        except asyncio.CancelledError:
            cancelled.set()
            raise
        except Exception:
            cancelled.set()
            # Do not leak provider errors/credentials or catalogue-independent model content.
            return self.result(
                "Optional inference failed or exhausted its limits. Use lookup for published facts.",
                status="unavailable",
                engine=request.engine,
            )
