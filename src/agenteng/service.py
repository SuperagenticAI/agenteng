"""One catalogue service used unchanged by CLI, MCP and A2A."""

from __future__ import annotations

import asyncio
import hmac
import re
import threading
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from .calendar import calendar
from .catalogue import load_catalogue
from .config import Settings
from .models import Catalogue, Event, Request, Result, Session, Speaker
from .participation import CITIES
from .tool_directory import TOOL_OPERATIONS, ToolDirectory, load_tool_directory


LONDON_ID = "agenteng-london-2026"


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


# Plain-English guide topics, first match wins. Checked after the registration desk
# and before tickets, so "Where is lunch?" never falls back to the events list.
PAST_FULLY_BOOKED = "The event was fully booked."


def long_date(iso: str) -> str:
    """2026-10-16 -> 16 October 2026."""
    day = date.fromisoformat(iso)
    return f"{day.day} {day.strftime('%B')} {day.year}"


A2A_TALKS_QUESTION = re.compile(r"\bagent[- ]to[- ]agent\b|\ba2a\b", re.I)
A2A_TALKS_WORDS = re.compile(r"\b(?:talks?|videos?|series|conversations?|clips?)\b", re.I)

GUIDE_TOPICS: tuple[tuple[str, str], ...] = (
    (
        "after",
        r"\bafter[- ]?(?:party|parties|event|the event|the conference|the talks|wards)\b"
        r"|\bwhat'?s on after\b|\bwhat is on after\b|\bafter\?|\bevening\b|\bpub\b",
    ),
    (
        "speaker-area",
        r"\bspeakers?'? ?(?:area|room|lounge)\b|\bgreen room\b"
        r"|\bwhere (?:do|should|can) (?:the )?speakers\b",
    ),
    (
        "help",
        r"\b(?:need|get|find|any) help\b|\bhelp on the day\b|\bstuck\b|\blost\b|\bemergency\b"
        r"|\bwho (?:do|can|should) i (?:contact|ask|talk to|message)\b"
        r"|\bcontact (?:someone|the organi[sz]ers?|for help|on the day)\b",
    ),
    ("social-area", r"\b(?:bar|social area|networking area|network)\b"),
    (
        "qna",
        r"\bq ?(?:&|and) ?a\b|\bqna\b|\bask (?:a|my|the|any) questions?\b"
        r"|\b(?:can|may) i ask\b|\bquestions? (?:for|to) (?:the )?speakers?\b",
    ),
    (
        "photography",
        r"\b(?:photos?|photograph\w*|pictures?|camera|film(?:ing)?|content creat\w*)\b",
    ),
    ("phones", r"\b(?:phones?|laptops?|mobile|silent|do (?:some )?work|work on)\b"),
    ("seating", r"\b(?:seats?|seating|sit|sitting)\b"),
    (
        "lunch",
        r"\b(?:lunch|food|eat|eating|pizzas?|dietary|diet|allerg\w*|vegan|vegetarian"
        r"|coffee|tea|drinks?|pastr\w*|breakfast|snacks?|refreshments?)\b",
    ),
)


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
        # Ticket terms and old "buy on Luma / £ price" FAQ text are retired for fully
        # booked events: never cited and never offered as search excerpts.
        booked = {e.id for e in self.catalogue.events if e.registration_status == "fully_booked"}
        self.retired_sources = {
            s.id
            for s in self.catalogue.sources
            if s.event_id in booked
            and (
                s.kind == "tickets"
                or (
                    s.kind == "faq"
                    and re.search(r"£\s?\d|\bget your ticket\b", s.text, re.IGNORECASE)
                )
            )
        }
        # Optional inference is serialized per process; it is operator-only.
        self._model_slot = threading.Lock()
        self._chat_runtime = None

    def authorized(self, token: str | None) -> bool:
        expected = self.settings.operator_token
        return bool(expected and token and hmac.compare_digest(expected.encode(), token.encode()))

    def a2a_talks_result(self, tag: str = "") -> Result:
        """AI-generated Agent-to-Agent videos. Kept apart from speakers, talks and sessions."""
        page = self.catalogue.a2a_talks
        if page is None:
            return self.result(
                "No Agent-to-Agent (A2A) Talks are published in this catalogue.",
                [],
                status="not_found",
            )
        wanted = re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")
        videos = [v for v in page.videos if not wanted or wanted in {v.tag, v.id, v.session}]
        data = {
            "title": page.title,
            "url": str(page.url),
            "intro": page.intro,
            "disclaimer": page.disclaimer,
            "ai_generated": True,
            "part_of_programme": False,
            "videos": [v.model_dump(mode="json") for v in videos],
        }
        return self.result(
            f"{len(videos)} Agent-to-Agent (A2A) Talk video(s). {page.disclaimer}",
            data,
            page.source_ids,
            status="ok" if videos else "not_found",
        )

    def result(self, answer: str, data=None, source_ids=(), **kwargs) -> Result:
        now = self.clock()
        return Result(
            answer=answer,
            data={} if data is None else data,
            sources=[
                self.sources[s] for s in dict.fromkeys(source_ids) if s not in self.retired_sources
            ],
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
        data = {**event.model_dump(mode="json"), "state": self.state(event)}
        if data["state"] == "past" and event.registration_status == "fully_booked":
            data["registration_note"] = PAST_FULLY_BOOKED
        titles = {
            s.speaker_id: s.title
            for s in self.catalogue.sessions
            if s.event_id == event.id and s.speaker_id
        }
        lineup = [
            {
                "speaker_id": sp.id,
                "name": sp.name,
                "role": sp.role,
                "company": sp.company,
                "talk_title": titles.get(sp.id) or sp.talk_title,
            }
            for sp in self.catalogue.speakers
            if event.id in sp.event_ids
        ]
        if lineup:
            data["lineup"] = lineup
        gallery = [t for t in self.catalogue.talks if t.event_id == event.id and t.gallery]
        links = self.catalogue.site_links
        if gallery and links:
            data["gallery_url"] = str(
                links.london_videos if gallery[0].gallery == "london" else links.gallery
            )
            data["gallery_count"] = len(gallery)
        return data

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

    def past_live_answer(self, request: Request, event: Event, now, current) -> Result:
        """Now/next after the event: past tense, never 'Now:' or 'Next:'."""
        day = long_date(event.date)
        agenda_url = next(
            (
                str(self.sources[i].url)
                for s in self.catalogue.sessions
                if s.event_id == event.id
                for i in s.source_ids
                if i in self.sources
            ),
            None,
        )
        base = {"event_id": event.id, "state": "past", "as_of": now.isoformat()}
        if request.operation == "now" and request.at is not None:
            at = f"{now:%H:%M}"
            if current:
                payload = self.talk_payload(current)
                by = payload.get("speaker_name")
                answer = f"At {at} on {day}: {current.title}" + (
                    f" (presented by {by})." if by else "."
                )
                return self.result(
                    answer,
                    {**base, "heading": f"At {at} on {day}", "session": payload},
                    current.source_ids,
                )
            return self.result(
                f"Nothing was scheduled at {at} on {day} in the published agenda.",
                {**base, "session": None},
                event.source_ids,
                status="not_found",
            )
        return self.result(
            f"{event.title} ended on {day}. Nothing is on now or next. "
            f"See the published agenda"
            + (f" at {agenda_url}" if agenda_url else "")
            + f" or run agenteng agenda {event.id}.",
            {**base, "session": None, "agenda_url": agenda_url},
            event.source_ids,
        )

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

    TALK_STATUS = {
        "upcoming": "Upcoming",
        "recording-coming-soon": "Recording coming soon",
        "recorded": "Recorded",
    }

    def gallery_payload(self, talk) -> dict:
        """A talks.ts row (/gallery/<slug>), joined with its session when one exists."""
        session = None
        if talk.session_id:
            session = self.session_map().get(talk.session_id)
        elif talk.speaker and talk.event_id:
            session = next(
                (
                    s
                    for s in self.catalogue.sessions
                    if s.event_id == talk.event_id and s.speaker_id == talk.speaker.slug
                ),
                None,
            )
        payload = (
            self.talk_payload(session)
            if session
            else {
                "id": None,
                "event_id": talk.event_id,
                "title": talk.title,
                "talk_title": talk.title,
                "kind": talk.kind,
                "abstract": None,
                "disciplines": [],
                "speaker_name": talk.speaker.name if talk.speaker else None,
                "speaker_role": talk.speaker.role if talk.speaker else None,
                "speaker_company": talk.speaker.company if talk.speaker else None,
                "source_ids": [],
            }
        )
        payload["session_id"] = session.id if session else None
        payload.update(
            {
                "slug": talk.slug,
                "title": talk.title,
                "gallery_kind": talk.kind,
                "city": talk.city,
                "event_name": talk.event_name,
                "event_url": str(talk.event_url),
                "date": talk.date,
                "topics": list(talk.topics),
                "status": talk.status,
                "status_label": self.TALK_STATUS[talk.status],
                "youtube_id": talk.youtube_id,
                "video_url": (
                    f"https://www.youtube.com/watch?v={talk.youtube_id}"
                    if talk.youtube_id
                    else None
                ),
                "ai_generated": talk.ai_generated,
                "talk_url": str(talk.url),
                "gallery": talk.gallery,
                "source_ids": list(dict.fromkeys([*talk.source_ids, *payload["source_ids"]])),
            }
        )
        if talk.ai_generated:
            payload["label"] = "AI-generated video, not a conference talk"
        if talk.transcript:
            payload["transcript"] = talk.transcript
        return payload

    def talks_result(self, request: Request, ids: set[str]) -> Result:
        """gallery mirrors /gallery (A2A last, opt-in); talks lists programme talks.

        talk (one item) looks in both, so any gallery slug, session ID or speaker ID works.
        """
        mode = request.operation
        gallery_mode = mode == "gallery"
        city = (request.city or "").casefold()
        online = city == "online"
        include_a2a = gallery_mode and (request.include_a2a or online) or mode == "talk"
        gallery_sessions = set()
        rows: list[dict] = []
        a2a_rows: list[dict] = []
        for talk in self.catalogue.talks:
            payload = self.gallery_payload(talk)
            if payload["session_id"]:
                gallery_sessions.add(payload["session_id"])
            if gallery_mode and not talk.gallery:
                continue
            if mode == "talks" and talk.kind != "talk":
                continue
            if talk.kind == "a2a":
                if include_a2a and not request.event_id and not request.speaker_id:
                    a2a_rows.append(payload)
                continue
            if online or (talk.event_id not in ids and talk.city.casefold() != city):
                continue
            if request.event_id and talk.event_id != request.event_id:
                continue
            rows.append(payload)
        if not online and not gallery_mode:
            for session in self.catalogue.sessions:
                if (
                    session.id not in gallery_sessions
                    and session.event_id in ids
                    and (session.kind == "talk" or session.speaker_id)
                ):
                    payload = self.talk_payload(session)
                    recording = next(
                        (
                            t
                            for t in self.catalogue.talks
                            if t.event_id == session.event_id and t.kind == "event-recording"
                        ),
                        None,
                    )
                    if recording:
                        payload["status_label"] = "In the full-event recording"
                        payload["recording_slug"] = recording.slug
                    rows.append(payload)
        rows += a2a_rows
        if request.session_id:
            key = request.session_id
            rows = [r for r in rows if key in {r.get("slug"), r.get("id"), r.get("session_id")}]
        if request.speaker_id:
            rows = [r for r in rows if r.get("speaker_id") == request.speaker_id]
        if request.topic:
            wanted = terms(request.topic)
            rows = [
                r
                for r in rows
                if wanted
                & terms(" ".join([*r.get("topics", []), *r.get("disciplines", []), r["title"]]))
            ]
        wanted = terms(request.query)
        if wanted:
            speakers = self.speaker_map()

            def score(r: dict) -> int:
                text = " ".join(
                    [
                        r.get("title") or "",
                        " ".join(r.get("topics") or []),
                        r.get("abstract") or "",
                        r.get("speaker_name") or "",
                        " ".join(
                            self.sources[i].text for i in r["source_ids"] if i in self.sources
                        ),
                        speakers[r["speaker_id"]].name if r.get("speaker_id") in speakers else "",
                    ]
                )
                return len(wanted & terms(text))

            scored = [(score(r), n, r) for n, r in enumerate(rows)]
            rows = [r for sc, n, r in sorted(scored, key=lambda x: (-x[0], x[1])) if sc]
        if request.operation == "talk":
            if not rows:
                return self.result("No published talk matched.", status="not_found")
            row = rows[0]
            status = f" {row['status_label']}." if row.get("status_label") else ""
            return self.result(f"Talk: {row['title']}.{status}", row, row["source_ids"])
        rows = rows[: request.limit]
        if gallery_mode:
            answer = f"{len(rows)} gallery item(s)."
            if any(r.get("gallery") == "london" for r in rows) and self.catalogue.site_links:
                answer += (
                    f" AgentEng London 2026 recordings: {self.catalogue.site_links.london_videos}"
                )
        else:
            answer = f"{len(rows)} published talk(s)."
        if any(r.get("ai_generated") for r in rows):
            answer += " A2A talks are listed last and are separate from the speaker programme."
            if self.catalogue.a2a_talks:
                answer += " " + self.catalogue.a2a_talks.disclaimer
        return self.result(
            answer,
            rows,
            [i for r in rows for i in r["source_ids"]],
            status="ok" if rows else "not_found",
        )

    def site_disciplines(self, result: Result) -> None:
        """All site disciplines (disciplines.ts), with directory tool counts where listed."""
        if not self.catalogue.disciplines:
            return
        listed = {row["id"]: row for row in result.data.get("items", [])}
        rows = []
        for d in self.catalogue.disciplines:
            row = {"id": d.id, "name": d.title, "short": d.short, "description": d.description}
            if d.id in listed:
                row.update(
                    tool_count=listed[d.id]["tool_count"],
                    total_tool_count=listed[d.id]["total_tool_count"],
                    in_directory=True,
                )
            else:
                row.update(
                    tool_count=None,
                    total_tool_count=None,
                    in_directory=False,
                    note="no tool listings yet",
                )
            rows.append(row)
        result.data["items"] = rows
        missing = [r["name"] for r in rows if not r["in_directory"]]
        result.answer = (
            f"{len(rows)} agent-engineering disciplines from the conference site; "
            f"{len(rows) - len(missing)} have tool listings. Tools can appear in several disciplines."
        )
        if missing:
            result.answer += f" {' and '.join(missing)}: no tool listings yet."

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

    def default_conference(self) -> Event | None:
        """The one upcoming or ongoing conference with a published day guide (London 2026)."""
        guide = self.catalogue.guide
        event = self.events.get(guide.event_id) if guide else None
        if event and self.state(event) in {"upcoming", "ongoing"}:
            return event
        return None

    def named_city(self, request: Request) -> str | None:
        plain = request.query.casefold()
        city = request.city or next((c for c in CITIES if c.casefold() in plain), None)
        if not city and re.search(r"\bsf\b", plain):
            city = "San Francisco"
        return city

    def past_conference(self) -> Event | None:
        """The guide event once it is over, while no other day-guide conference is upcoming."""
        guide = self.catalogue.guide
        event = self.events.get(guide.event_id) if guide else None
        return event if event and self.state(event) == "past" else None

    def past_event_day_answer(self, request: Request, query_terms: set[str]) -> Result | None:
        """After the event: doors and ticket questions answer in the past tense."""
        event = self.past_conference()
        guide = self.catalogue.guide
        if not event or not guide:
            return None
        city = self.named_city(request)
        if request.event_id and request.event_id != event.id:
            return None
        if city and city.casefold() != event.city.casefold():
            return None
        plain = request.query.casefold()
        held = f"{event.title} took place on {long_date(event.date)} at {event.venue}."
        timed = self.time_answer(request, event, plain)
        if timed is not None:
            return timed
        speaker = (
            None
            if re.search(r"\b(?:session|talk|start|starts|time|when|where|presenting)\b", plain)
            else self.speaker_named(plain, event.id)
        )
        if speaker is not None:
            return self.lookup(Request(operation="speaker", speaker_id=speaker.id))
        if query_terms & {"ticket", "tickets", "sold", "buy", "booked", "register", "registration"}:
            return self.lookup(Request(operation="tickets", event_id=event.id))
        if query_terms & {"agenda", "programme", "program", "schedule", "running"}:
            return self.lookup(
                Request(operation="agenda", event_id=event.id, limit=request.limit or 20)
            )
        times = query_terms & {"doors", "arrival", "arrive", "arriving", "checkin"} or (
            re.search(r"\bwhat time\b|\b(?:open|opens|start|starts|begin|begins)\b", plain)
            and not re.search(r"\b(?:talk|talks|session|sessions|speaker|next)\b", plain)
        )
        venue = guide.venue
        if times and venue:
            return self.result(
                f"{event.title} took place on {long_date(event.date)} at {event.venue}. "
                f"Doors opened at {venue.doors} and the programme started at "
                f"{venue.programme_starts.replace(' sharp', '')}.",
                {
                    "event_id": event.id,
                    "state": "past",
                    "facts": [f.model_dump() for f in guide.facts],
                    "day_guide_url": str(guide.url),
                },
                [i for i in ("guide", "guide-arriving") if i in self.sources],
            )
        directions = query_terms & {"directions", "venue", "everyman", "address", "located"} or (
            re.search(r"\bget (?:to|there)\b", plain)
        )
        if directions and venue:
            return self.result(
                f"{held} {venue.getting_there}",
                {
                    "event_id": event.id,
                    "state": "past",
                    "venue": event.venue,
                    "getting_there": venue.getting_there,
                    "walk_video_url": str(venue.walk_video_url) if venue.walk_video_url else None,
                },
                venue.source_ids,
            )
        topic = next((sid for sid, pattern in GUIDE_TOPICS if re.search(pattern, plain)), None)
        if topic and topic != "help" and topic in {s.id for s in guide.sections}:
            return self.result(
                f"{held} The day guide is kept for reference at {guide.url}#{topic}.",
                {
                    "event_id": event.id,
                    "state": "past",
                    "section": topic,
                    "day_guide_url": str(guide.url),
                },
                [i for i in (f"guide-{topic}",) if i in self.sources],
            )
        return None

    def event_day_answer(self, request: Request, query_terms: set[str]) -> Result | None:
        """Doors, directions, registration desk and ticket questions for the guide event.

        With no city named, questions default to the single upcoming conference while it
        is upcoming or today. A named San Francisco question is left to the normal routes.
        """
        guide = self.catalogue.guide
        default = self.default_conference()
        if not guide or not default:
            return self.past_event_day_answer(request, query_terms)
        city = self.named_city(request)
        if request.event_id and request.event_id != default.id:
            return None
        if city and city.casefold() != default.city.casefold():
            return None
        plain = request.query.casefold()
        sections = {s.id: s for s in guide.sections}
        venue = guide.venue

        def section_payload(*ids):
            return [sections[i].model_dump(mode="json") for i in ids if i in sections]

        def cite(*ids):
            return [i for i in ids if i in self.sources]

        venue_ids = venue.source_ids if venue else []
        timed = self.time_answer(request, default, plain)
        if timed is not None:
            return timed
        speaker = (
            None
            if re.search(r"\b(?:session|talk|start|starts|time|when|where|presenting)\b", plain)
            else self.speaker_named(plain, default.id)
        )
        if speaker is not None:
            return self.lookup(Request(operation="speaker", speaker_id=speaker.id))
        if re.search(r"\bwhere\b.*\b(?:registration|register|check[- ]?in|badges?)\b", plain) or (
            re.search(r"\b(?:registration desk|check[- ]?in desk)\b", plain)
        ):
            where = venue.registration if venue else ""
            first = sections["registration"].paragraphs[0] if "registration" in sections else ""
            rest = " ".join(re.split(r"(?<=\.)\s+", first)[1:]) if where else first
            return self.result(
                f"{where} {rest}".strip(),
                {
                    "event_id": default.id,
                    "registration": where,
                    "sections": section_payload("registration"),
                    "day_guide_url": str(guide.url),
                },
                cite(*venue_ids, "guide-registration"),
            )
        topic = next((sid for sid, pattern in GUIDE_TOPICS if re.search(pattern, plain)), None)
        if topic == "help" and query_terms & {
            "proposal",
            "proposals",
            "propose",
            "talk",
            "sponsor",
        }:
            topic = None
        if topic and topic in sections:
            row = sections[topic]
            answer = " ".join(row.paragraphs)
            data = {
                "event_id": default.id,
                "section": topic,
                "sections": section_payload(topic),
                "day_guide_url": str(guide.url),
            }
            if topic == "help":
                data["help"] = guide.help.model_dump(mode="json")
                answer += " " + "; ".join(f"{link.label}: {link.url}" for link in guide.help.online)
            return self.result(answer, data, cite(f"guide-{topic}"))
        ticket_words = {
            "ticket",
            "tickets",
            "sold",
            "buy",
            "booked",
            "price",
            "prices",
            "cost",
            "availability",
            "register",
            "registration",
        }
        if query_terms & ticket_words:
            return self.lookup(
                Request(operation="tickets", event_id=default.id, limit=request.limit)
            )
        times = query_terms & {"doors", "arrival", "arrive", "arriving", "checkin", "early"} or (
            re.search(r"\bwhat time\b|\b(?:open|opens|start|starts|begin|begins)\b", plain)
            and not re.search(r"\b(?:talk|talks|session|sessions|speaker|next)\b", plain)
        )
        if times and venue:
            return self.result(
                f"Doors {venue.doors}. Arrive {venue.arrive}, be seated by {venue.seated_by}; "
                f"the programme starts {venue.programme_starts}. {default.venue}.",
                {
                    "event_id": default.id,
                    "facts": [f.model_dump() for f in guide.facts],
                    "sections": section_payload("arriving"),
                    "day_guide_url": str(guide.url),
                },
                cite("guide", "guide-arriving"),
            )
        directions = query_terms & {
            "directions",
            "venue",
            "everyman",
            "station",
            "tube",
            "elizabeth",
            "jubilee",
            "dlr",
            "address",
            "located",
            "location",
            "walk",
        } or re.search(
            r"\bget (?:to|there)\b|\bhow (?:do|can|should) (?:i|we|you) find (?:it|the|everyman)\b",
            plain,
        )
        if directions and venue:
            return self.result(
                f"{default.venue}. "
                + (
                    f"Best way in: {venue.best_way_in} "
                    if venue.best_way_in
                    else f"{venue.getting_there} "
                )
                + f"Walk video: {venue.walk_video_url}",
                {
                    "event_id": default.id,
                    "venue": default.venue,
                    "best_way_in": venue.best_way_in,
                    "getting_there": venue.getting_there,
                    "walk_video_url": str(venue.walk_video_url) if venue.walk_video_url else None,
                    "registration": venue.registration,
                    "sections": section_payload("getting-here"),
                    "day_guide_url": str(guide.url),
                },
                cite(*venue_ids, "guide-getting-here"),
            )
        return None

    def speaker_named(self, plain: str, event_id: str) -> Speaker | None:
        """A published speaker whose full name (or unique surname) appears in the question."""
        speakers = [s for s in self.catalogue.speakers if event_id in s.event_ids]
        full = [s for s in speakers if s.name.casefold() in plain]
        if len(full) == 1:
            return full[0]
        surname = [
            s
            for s in speakers
            if len(s.name.split()) > 1
            and re.search(rf"\b{re.escape(s.name.split()[-1].casefold())}\b", plain)
        ]
        return surname[0] if len(surname) == 1 else None

    def time_answer(self, request: Request, event: Event, plain: str) -> Result | None:
        """Next talk, what's on now and 'who is speaking at HH:MM' for the default event."""
        clock = re.search(r"\b(?:at\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)\b", plain)
        if clock and re.search(r"\b(?:speak\w*|talk\w*|on|session|happening|presenting)\b", plain):
            local = datetime.fromisoformat(
                f"{event.date}T{int(clock.group(1)):02d}:{clock.group(2)}:00"
            ).replace(tzinfo=ZoneInfo(event.timezone))
            return self.lookup(Request(operation="now", event_id=event.id, at=local))
        if re.search(
            r"\bnext (?:talk|session|speaker|up)\b|\bwhat'?s next\b|\bwhat is next\b|\bup next\b",
            plain,
        ):
            return self.lookup(Request(operation="next", event_id=event.id))
        if re.search(
            r"\bwhat'?s on now\b|\bwhat is on now\b|\bhappening now\b|\bon stage now\b|"
            r"\bcurrent (?:talk|session)\b|\bwho is speaking now\b",
            plain,
        ):
            return self.lookup(Request(operation="now", event_id=event.id))
        return None

    def lookup(self, request: Request) -> Result:
        if request.operation == "chat":
            return self.lookup(Request(operation="ask", query=request.query, limit=request.limit))
        if request.operation in TOOL_OPERATIONS:
            result = self.tool_directory.lookup(request, self.clock(), self.settings.max_age_hours)
            if request.operation == "disciplines" and isinstance(result.data, dict):
                self.site_disciplines(result)
            return result
        if request.event_id and request.event_id not in self.events:
            return self.result(
                "Unknown event_id. Use events to list published event IDs.", status="not_found"
            )
        if request.operation == "discover":
            from .discovery import coming_label, discovery, featured_events

            answer = "Agent Engineering HQ runs AgentEng conferences and technical events in London and San Francisco."
            if request.city:
                ahead = [
                    e
                    for e in featured_events(self)
                    if e.city.casefold() == request.city.casefold()
                    and self.state(e) in {"upcoming", "ongoing"}
                ]
                if ahead:
                    answer += (
                        f" Next in {ahead[0].city}: {ahead[0].title}, {long_date(ahead[0].date)}."
                    )
                nxt = self.catalogue.site_links.next_event if self.catalogue.site_links else None
                if nxt and nxt.name.casefold().endswith(request.city.casefold()):
                    answer += f" {nxt.name} is {coming_label(nxt)}: {nxt.url}"
            return self.result(
                answer,
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
        if request.operation == "a2a-talks":
            return self.a2a_talks_result(request.topic or request.query)
        if request.operation == "ask":
            from .chat_context import focused_search, published_talk_answer

            if A2A_TALKS_QUESTION.search(request.query) and A2A_TALKS_WORDS.search(request.query):
                return self.a2a_talks_result("")

            if terms(request.query) & {"travel", "accommodation", "visa", "visas"}:
                return focused_search(self, request.query, request.limit, allow_faq=True)

            query_terms = terms(request.query)
            event_day = self.event_day_answer(request, query_terms)
            if event_day is not None:
                return event_day
            talk_answer = published_talk_answer(self, request)
            if talk_answer is not None:
                return talk_answer
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
            default = self.default_conference() if not city else None
            # Once the guide event is over and nothing else is current, its
            # published agenda and registration status stay the default answer.
            recent = self.past_conference() if not current else None
            if recent and city and city.casefold() != recent.city.casefold():
                recent = None
            target = (
                request.event_id
                or (current[0].id if len(current) == 1 else None)
                or (default.id if default else None)
                or (recent.id if recent else None)
            )
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
        if request.operation in {"talks", "talk", "gallery"}:
            return self.talks_result(request, ids)
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
            guide = self.catalogue.guide
            if guide and guide.event_id == event.id and guide.venue:
                directions = guide.venue.model_dump(mode="json")
                source_ids.extend(directions.pop("source_ids"))
                directions.pop("address", None)
                past = self.state(event) == "past"
                if past:
                    # Doors, arrival times and on-the-day help only matter before the event.
                    for key in ("doors", "arrive", "seated_by", "programme_starts"):
                        directions.pop(key, None)
                data.update(directions)
                data["day_guide_url"] = str(guide.url)
                if not past:
                    data["help"] = guide.help.model_dump(mode="json")
            data["state"] = self.state(event)
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
        if request.operation in {"about", "hq", "guide", "live", "bingo"}:
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
            if self.state(event) == "past":
                return self.past_live_answer(request, event, now, current)
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
            agenda_event = self.events.get(request.event_id or "") or (
                events[0] if len(events) == 1 else None
            )
            return self.result(
                f"{len(rows)} agenda entry/entries matched. This is the published agenda"
                + (
                    f" from {long_date(agenda_event.date)}."
                    if agenda_event and self.state(agenda_event) == "past"
                    else ". The event is fully booked; see the day guide for arriving and getting here."
                    if agenda_event and agenda_event.registration_status == "fully_booked"
                    else "; attendance is subject to registration."
                ),
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
            if event.registration_status == "fully_booked":
                guide = self.catalogue.guide
                past = self.state(event) == "past"
                guide_url = (
                    str(guide.url) if guide and guide.event_id == event.id and not past else None
                )
                note = PAST_FULLY_BOOKED if past else event.registration_note or "Fully booked."
                return self.result(
                    f"{event.title}: {note}" + (f" Day guide: {guide_url}" if guide_url else ""),
                    {
                        "event_id": event.id,
                        "registration_status": "fully_booked",
                        "registration_note": note,
                        "current_offers": [],
                        "published_offers": [],
                        "state": self.state(event),
                        "day_guide_url": guide_url,
                        "live_availability_verified": False,
                    },
                    [
                        i
                        for i in [*event.source_ids, *([] if past else ["guide-seating"])]
                        if i in self.sources
                        and self.sources[i].kind
                        not in ({"tickets", "guide"} if past else {"tickets"})
                    ],
                )
            return self.result(
                "Published price window only. Availability and approval must be confirmed on the registration page.",
                {
                    "event_id": event.id,
                    "registration_status": event.registration_status or "open",
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
            rows = [
                {
                    "event_id": e.id,
                    "title": e.title,
                    "url": str(e.recording_url),
                    "source_ids": list(e.source_ids),
                }
                for e in events
                if e.recording_url
            ]
            seen = {r["url"] for r in rows}
            for talk in self.catalogue.talks:
                url = (
                    f"https://www.youtube.com/watch?v={talk.youtube_id}"
                    if talk.youtube_id
                    else None
                )
                video = {
                    str(u) for e in events if e.id == talk.event_id for u in [e.recording_url] if u
                }
                if talk.kind == "a2a" or not url or talk.event_id not in ids or video & {url}:
                    continue
                if any(talk.youtube_id in u for u in seen | video):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "event_id": talk.event_id,
                        "title": talk.title,
                        "url": url,
                        "slug": talk.slug,
                        "talk_url": str(talk.url),
                        "source_ids": list(talk.source_ids),
                    }
                )
            links = self.catalogue.site_links
            if links and LONDON_ID in ids and "london-videos" in self.sources:
                rows.insert(
                    0,
                    {
                        "event_id": LONDON_ID,
                        "title": "AgentEng London 2026 recordings",
                        "url": str(links.london_videos),
                        "kind": "page",
                        "source_ids": ["london-videos"],
                    },
                )
            rows = rows[: request.limit]
            answer = f"{len(rows)} published recording link(s)."
            if any(
                t.status == "recording-coming-soon" and t.event_id in ids
                for t in self.catalogue.talks
            ):
                answer += (
                    " The AgentEng London 2026 welcome video is out and the talk recordings"
                    " are coming soon: run agenteng gallery --city London."
                )
            return self.result(
                answer,
                rows,
                [s for r in rows for s in r["source_ids"]],
                status="ok" if rows else "not_found",
            )
        # Search/ask returns literal, attributed excerpts. It never paraphrases with a model.
        wanted = terms(request.query)
        a2a_wanted = bool(A2A_TALKS_QUESTION.search(request.query))
        candidates = [
            s
            for s in self.catalogue.sources
            if s.id not in self.retired_sources
            and (s.kind != "a2a-talks" or a2a_wanted)
            and (
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
            else "No published sources matched. Try events, agenda, guide or a more specific query."
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
