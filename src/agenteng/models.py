"""Shared, strictly validated catalogue and protocol contracts."""

import re
from datetime import date as calendar_date
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, HttpUrl, field_validator, model_validator

from .contracts import Model
from .tool_directory import TOOL_OPERATIONS, DisciplineID, ToolKind


class Source(Model):
    id: str
    url: HttpUrl
    text: str
    event_id: str | None = None
    kind: str = "document"


class SpeakerLinks(Model):
    x: HttpUrl | None = None
    linkedin: HttpUrl | None = None
    github: HttpUrl | None = None
    website: HttpUrl | None = None


class SpeakerLocation(Model):
    city: str | None = None
    country: str


class SpeakerProject(Model):
    name: str
    url: HttpUrl
    blurb: str = ""


class Speaker(Model):
    id: str
    name: str
    role: str = ""
    company: str = ""
    company_url: HttpUrl | None = None
    note: str | None = None
    location: SpeakerLocation | None = None
    links: SpeakerLinks | None = None
    projects: list[SpeakerProject] = Field(default_factory=list)
    announced_on: str | None = None
    disciplines: list[str] = Field(default_factory=list)
    event_ids: list[str]
    talk_title: str | None = None
    abstract: str | None = None
    source_ids: list[str]


class Session(Model):
    id: str
    event_id: str
    title: str
    kind: str
    start: datetime | None = None
    end: datetime | None = None
    speaker_id: str | None = None
    topics: list[str] = Field(default_factory=list)
    source_ids: list[str]


class Offer(Model):
    name: str
    amount: int = Field(ge=0)
    currency: str = "GBP"
    valid_from: datetime
    valid_until: datetime | None = None
    sold_out: bool = False


class Event(Model):
    id: str
    title: str
    city: str
    timezone: str
    date: str
    date_precision: Literal["day", "month"] = "day"
    venue: str
    venue_tour_url: HttpUrl | None = None
    page_url: HttpUrl | None = None
    track: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    cancelled: bool = False
    speaker_submission_status: Literal["not_announced", "invited_only"] = "not_announced"
    registration_url: HttpUrl | None = None
    recording_url: HttpUrl | None = None
    offers: list[Offer] = Field(default_factory=list)
    tagline: str | None = None
    registration_status: Literal["open", "fully_booked"] | None = None
    registration_note: str | None = None
    source_ids: list[str]

    @model_validator(mode="after")
    def validate_dates(self):
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown event timezone") from exc
        if self.date_precision == "day":
            if calendar_date.fromisoformat(self.date).isoformat() != self.date:
                raise ValueError("Dates must use YYYY-MM-DD")
        else:
            parsed = calendar_date.fromisoformat(self.date + "-01")
            if parsed.strftime("%Y-%m") != self.date:
                raise ValueError("Invalid month-only date")
        if (
            self.start
            and self.start.astimezone(ZoneInfo(self.timezone)).date().isoformat() != self.date
        ):
            raise ValueError("Event start does not match published local date")
        if self.date_precision == "month" and (self.start or self.end):
            raise ValueError("Month-only events cannot have invented timestamps")
        for stamp in [
            self.start,
            self.end,
            *[o.valid_from for o in self.offers],
            *[o.valid_until for o in self.offers],
        ]:
            if stamp is not None and stamp.utcoffset() is None:
                raise ValueError("Timestamps must include a timezone")
        if self.start and self.end and self.end <= self.start:
            raise ValueError("Event end must follow its start")
        if any(o.valid_until and o.valid_until <= o.valid_from for o in self.offers):
            raise ValueError("Offer validity window is reversed")
        return self


class FAQ(Model):
    id: str
    question: str
    answer: str
    event_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class Sponsor(Model):
    id: str
    name: str
    url: HttpUrl
    city: str
    blurb: str = ""


class SupportOption(Model):
    id: str
    title: str
    blurb: str


class Theme(Model):
    id: str
    title: str
    command: str
    description: str


class Link(Model):
    label: str
    url: HttpUrl


class Principle(Model):
    title: str
    description: str


class Reading(Model):
    title: str
    date: str
    url: HttpUrl


class HQ(Model):
    """Agent Engineering HQ page content, exported verbatim from the website."""

    url: HttpUrl
    summary: str
    cities: str = ""
    manifesto: list[str] = Field(default_factory=list)
    mindset: list[Principle] = Field(default_factory=list)
    further_reading_intro: str = ""
    further_reading: list[Reading] = Field(default_factory=list)
    source_ids: list[str]


class Organiser(Model):
    name: str
    url: HttpUrl
    blurb: str = ""


class Chair(Model):
    name: str
    title: str
    bio: str = ""
    links: list[Link] = Field(default_factory=list)


class Associate(Model):
    """Associate named on the published homepage chair card."""

    name: str
    url: str


class TrulyYours(Model):
    """Homepage tagline and the 'Why this one is truly yours' block."""

    tagline: str
    title: str
    text: str
    source_ids: list[str]


class About(Model):
    """Published definition, organiser and chair card from the website."""

    definition: str
    organiser: Organiser | None = None
    chair: Chair | None = None
    associates: list[Associate] = Field(default_factory=list)
    contact_email: str | None = None
    truly_yours: TrulyYours | None = None
    source_ids: list[str]


class GuideFact(Model):
    label: str
    value: str


class GuideLink(Model):
    label: str
    url: HttpUrl


class GuideSection(Model):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str
    paragraphs: list[str] = Field(min_length=1)
    links: list[GuideLink] = Field(default_factory=list)


class HelpPerson(Model):
    name: str
    role: str | None = None


class GuideHelp(Model):
    on_site: list[HelpPerson] = Field(default_factory=list)
    online: list[GuideLink] = Field(default_factory=list)


class GuideVenue(Model):
    """Directions and arrival times published on the homepage venue card and /guide."""

    address: str
    best_way_in: str | None = None
    getting_there: str = ""
    walk_video_url: HttpUrl | None = None
    registration: str = ""
    doors: str
    arrive: str
    seated_by: str
    programme_starts: str
    source_ids: list[str]


class Guide(Model):
    """The published /guide day guide for one event, exported from the website."""

    event_id: str
    url: HttpUrl
    title: str
    description: str = ""
    intro: str = ""
    hero_lead: dict[Literal["before", "eve", "today", "after"], str] = Field(default_factory=dict)
    facts: list[GuideFact] = Field(default_factory=list)
    sections: list[GuideSection] = Field(min_length=1)
    help: GuideHelp = Field(default_factory=GuideHelp)
    venue: GuideVenue | None = None
    source_ids: list[str]


CITY_ALIASES = {"london": "London", "san francisco": "San Francisco", "sf": "San Francisco"}


def canonical_city(value: str | None) -> str | None:
    """Accept website slugs such as ``san-francisco``; unknown cities pass through."""
    if value is None:
        return None
    key = re.sub(r"[-_\s]+", " ", value.strip().casefold())
    return CITY_ALIASES.get(key, value)


HQ_SECTIONS = ("manifesto", "mindset", "reading")
GUIDE_SECTION_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
ABOUT_SECTIONS = ("organiser", "chair", "connect")


class A2ATalk(Model):
    """One AI-generated Agent-to-Agent video. Never a speaker, talk or session."""

    id: str
    session: str
    title: str
    youtube_id: str
    url: HttpUrl
    tag: str
    duration_sec: int | None = None
    duration: str | None = None


class A2ATalks(Model):
    """The published /agent-to-agent page: AI-generated videos, separate from the programme."""

    url: HttpUrl
    title: str
    intro: str = ""
    disclaimer: str
    videos: list[A2ATalk] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class TalkSpeaker(Model):
    name: str
    role: str = ""
    company: str = ""
    slug: str


class Talk(Model):
    """One talk or video from the site's talks.ts (/gallery/<slug>, or /san-francisco)."""

    slug: str
    title: str
    kind: Literal["talk", "event-recording", "a2a"]
    city: str
    event_id: str | None = None
    event_name: str
    event_url: HttpUrl
    date: str | None = None
    speaker: TalkSpeaker | None = None
    topics: list[str] = Field(default_factory=list)
    youtube_id: str | None = None
    transcript: str | None = None
    ai_generated: bool = False
    status: Literal["upcoming", "recording-coming-soon", "recorded"]
    session_id: str | None = None
    gallery: Literal["london", "san-francisco", "a2a"] | None = None
    """Gallery tab on /gallery; None when the talk has no gallery page."""
    url: HttpUrl
    source_ids: list[str]


class SiteDiscipline(Model):
    id: str
    title: str
    short: str
    description: str


class SiteEventLink(Model):
    name: str
    when: str
    url: HttpUrl


class SiteLinks(Model):
    next_event: SiteEventLink | None = None
    previous_event: SiteEventLink | None = None
    london_2026: HttpUrl
    gallery: HttpUrl
    london_videos: HttpUrl
    agenteng: HttpUrl


class Catalogue(Model):
    schema_version: Literal[1] = 1
    version: str
    published_at: datetime
    source_commit: str
    source_hash: str
    events: list[Event]
    speakers: list[Speaker]
    sessions: list[Session]
    faqs: list[FAQ] = Field(default_factory=list)
    sponsors: list[Sponsor] = Field(default_factory=list)
    support_options: list[SupportOption] = Field(default_factory=list)
    themes: list[Theme] = Field(default_factory=list)
    hq: HQ | None = None
    about: About | None = None
    guide: Guide | None = None
    a2a_talks: A2ATalks | None = None
    talks: list[Talk] = Field(default_factory=list)
    disciplines: list[SiteDiscipline] = Field(default_factory=list)
    site_links: SiteLinks | None = None
    sources: list[Source]

    @model_validator(mode="after")
    def validate_references(self):
        if self.published_at.utcoffset() is None:
            raise ValueError("Publication time requires a timezone")
        for records in [
            self.events,
            self.speakers,
            self.sessions,
            self.faqs,
            self.sponsors,
            self.support_options,
            self.themes,
            self.sources,
        ]:
            if len({r.id for r in records}) != len(records):
                raise ValueError("Duplicate record IDs")
        events, speakers, sources = (
            {r.id for r in rows} for rows in [self.events, self.speakers, self.sources]
        )
        evidenced = [*self.events, *self.speakers, *self.sessions, *self.faqs]
        extra = [r for r in (self.hq, self.about, self.guide) if r]
        if self.about and self.about.truly_yours:
            extra.append(self.about.truly_yours)
        if self.guide and self.guide.venue:
            extra.append(self.guide.venue)
        if self.a2a_talks:
            extra.append(self.a2a_talks)
            if len({v.id for v in self.a2a_talks.videos}) != len(self.a2a_talks.videos):
                raise ValueError("Duplicate A2A talk IDs")
        if len({t.slug for t in self.talks}) != len(self.talks):
            raise ValueError("Duplicate talk slugs")
        for talk in self.talks:
            if talk.event_id is not None and talk.event_id not in events:
                raise ValueError("Talk references an unknown event")
        extra.extend(self.talks)
        if self.guide and self.guide.event_id not in events:
            raise ValueError("Guide references an unknown event")
        if self.guide and len({s.id for s in self.guide.sections}) != len(self.guide.sections):
            raise ValueError("Duplicate guide section IDs")
        for row in evidenced + extra:
            if not row.source_ids or not set(row.source_ids) <= sources:
                raise ValueError(f"Missing evidence for {getattr(row, 'id', type(row).__name__)}")
        for row in self.faqs:
            if row.event_id is not None and row.event_id not in events:
                raise ValueError("FAQ references an unknown event")
        for row in self.speakers:
            if not set(row.event_ids) <= events:
                raise ValueError("Unknown speaker event")
        for row in self.sessions:
            if row.event_id not in events or (row.speaker_id and row.speaker_id not in speakers):
                raise ValueError("Unknown session event/speaker")
            for stamp in [row.start, row.end]:
                if stamp and stamp.utcoffset() is None:
                    raise ValueError("Session timestamps require timezones")
            if row.start and row.end and row.end <= row.start:
                raise ValueError("Session end must follow start")
            event = next(e for e in self.events if e.id == row.event_id)
            if row.speaker_id:
                speaker = next(s for s in self.speakers if s.id == row.speaker_id)
                if row.event_id not in speaker.event_ids:
                    raise ValueError("Session speaker belongs to another event")
            if row.start and event.start and row.start < event.start:
                raise ValueError("Session starts before its event")
            if row.end and event.end and row.end > event.end:
                raise ValueError("Session ends after its event")
        if any(s.event_id is not None and s.event_id not in events for s in self.sources):
            raise ValueError("Source references an unknown event")
        return self


class ChatTurn(Model):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class Request(Model):
    operation: Literal[
        "events",
        "event",
        "agenda",
        "speakers",
        "speaker",
        "talks",
        "talk",
        "faq",
        "venue",
        "sponsors",
        "conduct",
        "themes",
        "about",
        "hq",
        "guide",
        "now",
        "next",
        "live",
        "bingo",
        "tickets",
        "recordings",
        "a2a-talks",
        "gallery",
        "search",
        "ask",
        "chat",
        "participate",
        "discover",
        "disciplines",
        "tools",
        "tool",
    ]
    event_id: str | None = Field(default=None, max_length=128)
    speaker_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=100)
    query: str = Field(default="", max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)
    topic: str | None = Field(default=None, max_length=200)
    upcoming: bool = False
    past: bool = False
    include_a2a: bool = False
    format: Literal["json", "ics", "text", "svg", "html"] = "json"
    section: str | None = Field(default=None, max_length=64)
    at: datetime | None = None
    seed: int | None = Field(default=None, ge=0, le=2**53)
    size: Literal[4, 5] = 5
    engine: Literal["lookup", "auto", "standard", "rlm"] = "lookup"
    limit: int = Field(default=20, ge=1, le=100)
    tool_id: str | None = Field(default=None, min_length=1, max_length=128)
    discipline: DisciplineID | None = None
    kind: ToolKind | None = None
    category: str | None = Field(default=None, min_length=1, max_length=160)
    offset: int = Field(default=0, ge=0, le=10000)
    tool_status: Literal["listed", "hold", "deprecated", "all"] = "listed"

    @field_validator("city")
    @classmethod
    def normalise_city(cls, value):
        return canonical_city(value)

    @model_validator(mode="after")
    def validate_operation(self):
        if self.history and self.operation != "chat":
            raise ValueError("Conversation history only applies to chat")
        if self.operation == "chat" and (
            self.engine not in {"lookup", "auto"}
            or self.event_id
            or self.city
            or self.topic
            or self.upcoming
            or self.past
        ):
            raise ValueError("Chat accepts a question and history, not engines or event filters")
        if self.section and not (
            (self.operation == "hq" and self.section in HQ_SECTIONS)
            or (self.operation == "about" and self.section in ABOUT_SECTIONS)
            or (self.operation == "guide" and re.match(GUIDE_SECTION_PATTERN, self.section))
        ):
            raise ValueError(
                "section applies to hq (manifesto, mindset, reading), "
                "about (organiser, chair, connect) or guide (a guide section id, or list)"
            )
        if self.at and self.operation not in {"now", "next", "live"}:
            raise ValueError("at only applies to now, next or live")
        if (self.seed is not None or self.size != 5) and self.operation != "bingo":
            raise ValueError("seed and size only apply to bingo")
        if self.format in {"text", "svg", "html"} and self.operation != "bingo":
            raise ValueError("text, svg and html output are only supported for bingo")
        if self.operation == "tool" and not self.tool_id:
            raise ValueError("tool requires tool_id")
        if self.tool_id and self.operation != "tool":
            raise ValueError("tool_id only applies to tool")
        if self.operation != "tools" and (
            self.discipline
            or self.kind
            or self.category
            or self.offset
            or self.tool_status != "listed"
        ):
            raise ValueError("Directory filters only apply to tools")
        if self.operation in TOOL_OPERATIONS and (
            self.event_id
            or self.city
            or self.upcoming
            or self.past
            or self.topic
            or self.speaker_id
            or self.session_id
        ):
            raise ValueError("Event filters do not apply to the tool directory")
        if self.operation in {"disciplines", "tool"} and self.query:
            raise ValueError("Directory search only applies to tools")
        if self.speaker_id and self.operation not in {
            "speaker",
            "talk",
            "talks",
            "speakers",
        }:
            raise ValueError("speaker_id only applies to speaker, talk, talks or speakers")
        if self.session_id and self.operation not in {"talk", "agenda"}:
            raise ValueError("session_id only applies to talk or agenda")
        if self.upcoming and self.past:
            raise ValueError("Choose upcoming or past, not both")
        if self.operation in {"event", "agenda", "tickets", "venue"} and not self.event_id:
            raise ValueError(f"{self.operation} requires event_id")
        if self.operation == "speaker" and not self.speaker_id:
            raise ValueError("speaker requires speaker_id")
        if (
            self.operation == "talk"
            and not self.session_id
            and not self.speaker_id
            and not self.query.strip()
        ):
            raise ValueError("talk requires session_id, speaker_id or query")
        if self.operation in {"ask", "search", "chat"} and not self.query.strip():
            raise ValueError(f"{self.operation} requires query")
        if self.engine not in {"lookup", "auto"} and self.operation != "ask":
            raise ValueError("Model engines only apply to ask")
        if self.format == "ics" and self.operation not in {"agenda"}:
            raise ValueError("ICS output is only supported for agenda")
        return self


class Result(Model):
    status: Literal["ok", "not_found", "unavailable", "error"] = "ok"
    answer: str
    data: dict | list = Field(default_factory=dict)
    sources: list[Source] = Field(default_factory=list)
    catalogue_version: str
    evaluated_at: datetime
    published_at: datetime
    stale: bool
    engine: str = "lookup"
    usage: dict = Field(default_factory=dict)
    artifact: str | None = None
