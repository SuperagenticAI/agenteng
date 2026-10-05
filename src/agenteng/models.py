"""Shared, strictly validated catalogue and protocol contracts."""

from datetime import date as calendar_date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, HttpUrl, StrictBool, model_validator

from .contracts import Model
from .participation import Draft, DRAFT_OPERATIONS, PRIVATE_OPERATIONS
from .tool_directory import DisciplineID, ToolKind, TOOL_OPERATIONS


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
    track: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    cancelled: bool = False
    speaker_submission_status: Literal["not_announced", "invited_only"] = "not_announced"
    registration_url: HttpUrl | None = None
    recording_url: HttpUrl | None = None
    offers: list[Offer] = Field(default_factory=list)
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
        for row in [*self.events, *self.speakers, *self.sessions, *self.faqs]:
            if not row.source_ids or not set(row.source_ids) <= sources:
                raise ValueError(f"Missing evidence for {row.id}")
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
        "now",
        "next",
        "save",
        "unsave",
        "my_agenda",
        "tickets",
        "recordings",
        "search",
        "plan",
        "ask",
        "participate",
        "discover",
        "disciplines",
        "tools",
        "tool",
        "proposal_draft",
        "proposal_preview",
        "proposal_export",
        "proposal_prepare",
        "proposal_submit",
        "proposal_status",
        "proposal_withdraw",
    ]
    event_id: str | None = Field(default=None, max_length=128)
    speaker_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=100)
    query: str = Field(default="", max_length=4000)
    topic: str | None = Field(default=None, max_length=200)
    upcoming: bool = False
    past: bool = False
    interests: list[Annotated[str, Field(max_length=200)]] = Field(
        default_factory=list, max_length=20
    )
    format: Literal["json", "ics"] = "json"
    engine: Literal["lookup", "auto", "standard", "rlm"] = "lookup"
    limit: int = Field(default=20, ge=1, le=100)
    tool_id: str | None = Field(default=None, min_length=1, max_length=128)
    discipline: DisciplineID | None = None
    kind: ToolKind | None = None
    category: str | None = Field(default=None, min_length=1, max_length=160)
    offset: int = Field(default=0, ge=0, le=10000)
    tool_status: Literal["listed", "hold", "deprecated", "all"] = "listed"
    draft: Draft | None = None
    draft_format: Literal["json", "markdown"] = "json"
    preview_reference: str | None = Field(default=None, min_length=32, max_length=128)
    receipt: str | None = Field(default=None, min_length=32, max_length=32, pattern="^[a-f0-9]+$")
    confirmed: StrictBool = False

    @model_validator(mode="after")
    def validate_operation(self):
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
            or self.interests
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
            "save",
            "unsave",
            "speakers",
        }:
            raise ValueError("speaker_id only applies to speaker, talk, talks, speakers or save")
        if self.session_id and self.operation not in {"talk", "save", "unsave", "agenda", "plan"}:
            raise ValueError("session_id only applies to talk, save, unsave, agenda or plan")
        draft_operations = DRAFT_OPERATIONS | {"proposal_prepare", "proposal_submit"}
        if self.operation in draft_operations and self.draft is None:
            raise ValueError("This proposal operation requires a draft")
        if self.operation not in draft_operations and self.draft is not None:
            raise ValueError("Draft content is only accepted by explicit draft operations")
        if self.operation == "proposal_submit" and not self.preview_reference:
            raise ValueError("Submission requires a prepared preview_reference")
        if self.preview_reference and self.operation != "proposal_submit":
            raise ValueError("Preview references only apply to submission")
        if self.operation in {"proposal_status", "proposal_withdraw"} and not self.receipt:
            raise ValueError("This operation requires a receipt")
        if self.receipt and self.operation not in {"proposal_status", "proposal_withdraw"}:
            raise ValueError("Receipt only applies to status or withdrawal")
        if self.confirmed and self.operation not in {"proposal_submit", "proposal_withdraw"}:
            raise ValueError("Confirmation only applies to submission or withdrawal")
        if self.operation in DRAFT_OPERATIONS | PRIVATE_OPERATIONS and (
            self.query or self.event_id or self.city or self.interests or self.topic
        ):
            raise ValueError("Proposal context belongs inside the draft")
        if self.upcoming and self.past:
            raise ValueError("Choose upcoming or past, not both")
        if self.operation in {"event", "agenda", "tickets", "plan", "venue"} and not self.event_id:
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
        if self.operation in {"save", "unsave"} and not self.session_id and not self.speaker_id:
            raise ValueError(f"{self.operation} requires session_id or speaker_id")
        if self.operation in {"ask", "search"} and not self.query.strip():
            raise ValueError(f"{self.operation} requires query")
        if self.engine not in {"lookup", "auto"} and self.operation != "ask":
            raise ValueError("Model engines only apply to ask")
        if self.format == "ics" and self.operation not in {"plan", "agenda", "my_agenda"}:
            raise ValueError("ICS output is only supported for plan, agenda or my_agenda")
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
