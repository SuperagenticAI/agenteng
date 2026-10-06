"""Rich human-readable renderers for AgentEng CLI results."""

from __future__ import annotations

from datetime import date, datetime

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Result
from .output import BLUE, MAGENTA, VIOLET, display_text, make_console

BOX = box.ROUNDED


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def friendly_date(event: dict) -> str:
    """Human date like 'Fri 16 Oct 2026' or 'Oct 2026' for month precision."""
    precision = event.get("date_precision") or "day"
    raw = event.get("date") or ""
    try:
        if precision == "month" and len(raw) >= 7:
            parsed = date.fromisoformat(raw[:7] + "-01")
            return parsed.strftime("%b %Y")
        parsed = date.fromisoformat(raw[:10])
    except ValueError:
        return raw
    return f"{parsed.strftime('%a')} {parsed.day} {parsed.strftime('%b %Y')}"


def event_label(event: dict) -> str:
    """Compact human label: title · city · date."""
    title = display_text(event.get("title")) or event.get("id") or "Event"
    city = event.get("city") or ""
    when = friendly_date(event)
    parts = [p for p in (title, city, when) if p]
    return " · ".join(parts)


def _fmt_money(amount: int, currency: str) -> str:
    symbol = {"GBP": "£", "USD": "$", "EUR": "€"}.get(currency, currency + " ")
    if currency in {"GBP", "USD", "EUR"}:
        return f"{symbol}{amount}"
    return f"{amount} {currency}"


def _cheapest_offer(offers: list[dict] | None) -> dict | None:
    available = [o for o in (offers or []) if not o.get("sold_out")]
    if not available:
        return None
    return min(available, key=lambda o: (o.get("amount", 0), o.get("name") or ""))


def _state_style(state: str) -> str:
    if state in {"upcoming", "ongoing"}:
        return "ae.ok"
    if state == "cancelled":
        return "ae.err"
    return "ae.meta"


def _footer(console: Console, result: Result) -> None:
    """Print supporting sources once each (by URL), preserving catalogue order."""
    seen: set[str] = set()
    for source in result.sources:
        key = str(source.url)
        if key in seen:
            continue
        seen.add(key)
        console.print(f"[ae.meta]Source:[/] {source.url} [{source.id}]")
    if result.stale:
        console.print(
            "[ae.warn]Catalogue snapshot is older than 48 hours; "
            "confirm current details on the linked website.[/]"
        )


def _panel(title: str, body, *, border: str = BLUE) -> Panel:
    return Panel(
        body,
        title=Text(display_text(title), style="ae.title"),
        border_style=border,
        box=BOX,
        padding=(0, 1),
        expand=True,
    )


def _event_card(event: dict) -> Panel:
    body = Text()
    city = event.get("city") or ""
    when = friendly_date(event)
    body.append(f"{city}  ·  {when}\n", style="ae.accent")
    if event.get("venue"):
        body.append(display_text(event["venue"]) + "\n")
    state = event.get("state") or ("cancelled" if event.get("cancelled") else "")
    if state:
        body.append("Status: ", style="ae.meta")
        body.append(state + "\n", style=_state_style(state))
    offer = _cheapest_offer(event.get("offers"))
    if offer:
        body.append("From ", style="ae.meta")
        body.append(
            _fmt_money(offer["amount"], offer.get("currency") or "GBP"),
            style="ae.price",
        )
        body.append(f" ({offer.get('name')})\n", style="ae.meta")
    elif event.get("offers"):
        body.append("Tickets: sold out in this snapshot\n", style="ae.sold")
    if event.get("registration_url"):
        body.append("Register: ", style="ae.meta")
        body.append(str(event["registration_url"]) + "\n", style=BLUE)
    if event.get("recording_url"):
        body.append("Recording: ", style="ae.meta")
        body.append(str(event["recording_url"]) + "\n", style=BLUE)
    eid = event.get("id")
    if eid:
        body.append(f"id: {eid}", style="ae.meta")
    return _panel(display_text(event.get("title")) or "Event", body, border=BLUE)


def render_events(console: Console, result: Result) -> None:
    events = result.data if isinstance(result.data, list) else []
    if not events:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    console.print(Text("Events", style="ae.title"))
    for event in events:
        console.print(_event_card(event))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_event_detail(console: Console, result: Result) -> None:
    events = result.data if isinstance(result.data, list) else []
    if not events:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    console.print(_event_card(events[0]))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def _speaker_body(speaker: dict, *, full: bool = False, include_abstract: bool = True) -> Text:
    """Build speaker card body.

    When a Session card will show the talk abstract, pass include_abstract=False
    so the abstract appears once.
    """
    body = Text()
    role = speaker.get("role") or ""
    company = speaker.get("company") or ""
    note = speaker.get("note") or ""
    meta = " · ".join(p for p in (role, company) if p)
    if meta:
        body.append(meta + "\n", style="ae.accent")
    if note:
        body.append(display_text(note) + "\n", style="ae.meta")
    location = speaker.get("location") or {}
    if location:
        place = ", ".join(p for p in (location.get("city"), location.get("country")) if p)
        if place:
            body.append(place + "\n", style="ae.meta")
    talk = speaker.get("talk_title")
    if talk and include_abstract:
        # Title only here when there is no separate session card.
        body.append("Talk: ", style="ae.meta")
        body.append(display_text(talk) + "\n")
    disciplines = speaker.get("disciplines") or []
    if disciplines:
        body.append("Disciplines: " + ", ".join(disciplines) + "\n", style="ae.meta")
    if full:
        if include_abstract:
            abstract = speaker.get("abstract")
            if abstract:
                body.append("\n")
                body.append(display_text(abstract) + "\n")
        links = speaker.get("links") or {}
        for label, key in (
            ("X", "x"),
            ("GitHub", "github"),
            ("LinkedIn", "linkedin"),
            ("Web", "website"),
        ):
            if links.get(key):
                body.append(f"{label}: ", style="ae.meta")
                body.append(str(links[key]) + "\n", style=BLUE)
        if speaker.get("company_url"):
            body.append("Company: ", style="ae.meta")
            body.append(str(speaker["company_url"]) + "\n", style=BLUE)
        for project in speaker.get("projects") or []:
            body.append(f"Project: {project.get('name')}", style="ae.accent")
            if project.get("blurb"):
                body.append(f" - {display_text(project['blurb'])}")
            body.append("\n")
            if project.get("url"):
                body.append(str(project["url"]) + "\n", style=BLUE)
    events = speaker.get("event_ids") or []
    if events:
        body.append("Events: " + ", ".join(events) + "\n", style="ae.meta")
    if speaker.get("id"):
        body.append(f"id: {speaker['id']}", style="ae.meta")
    return body


def render_speakers(console: Console, result: Result) -> None:
    speakers = result.data if isinstance(result.data, list) else []
    if not speakers:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    for speaker in speakers:
        console.print(
            _panel(
                speaker.get("name") or speaker.get("id") or "Speaker",
                _speaker_body(speaker, full=len(speakers) == 1),
                border=VIOLET,
            )
        )
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_speaker(console: Console, result: Result) -> None:
    speaker = result.data if isinstance(result.data, dict) else {}
    if not speaker:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    talk = speaker.get("talk")
    has_session = bool(talk and talk.get("start"))
    console.print(
        _panel(
            speaker.get("name") or speaker.get("id") or "Speaker",
            _speaker_body(speaker, full=True, include_abstract=not has_session),
            border=VIOLET,
        )
    )
    if has_session:
        console.print(_panel("Session", _talk_body(talk, include_title=True), border=BLUE))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def _talk_body(talk: dict, *, include_title: bool = True) -> Text:
    """Talk/session body. Long titles live in the body so panel headers stay short."""
    body = Text()
    when = ""
    start = _parse_dt(talk.get("start"))
    end = _parse_dt(talk.get("end"))
    if start and end:
        when = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    elif start:
        when = start.strftime("%H:%M")
    if when:
        body.append(when + "  ·  ", style="ae.accent")
    body.append((talk.get("kind") or "talk") + "\n", style="ae.meta")
    if include_title:
        title = talk.get("title") or talk.get("talk_title")
        if title:
            body.append(display_text(title) + "\n")
    if talk.get("speaker_name"):
        meta = " · ".join(
            p
            for p in (
                talk.get("speaker_name"),
                talk.get("speaker_role"),
                talk.get("speaker_company"),
            )
            if p
        )
        body.append(meta + "\n", style="ae.accent")
    abstract = talk.get("abstract")
    if abstract:
        body.append(display_text(abstract) + "\n")
    disciplines = talk.get("disciplines") or talk.get("topics") or []
    if disciplines:
        body.append(", ".join(disciplines) + "\n", style="ae.meta")
    if talk.get("id"):
        body.append(f"id: {talk['id']}", style="ae.meta")
    return body


def render_talks(console: Console, result: Result) -> None:
    talks = result.data if isinstance(result.data, list) else []
    if not talks:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    for talk in talks:
        # Short panel header; full title wraps in the body.
        console.print(_panel("Talk", _talk_body(talk, include_title=True), border=VIOLET))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_talk(console: Console, result: Result) -> None:
    talk = result.data if isinstance(result.data, dict) else {}
    if not talk:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    console.print(_panel("Talk", _talk_body(talk, include_title=True), border=VIOLET))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_faq(console: Console, result: Result) -> None:
    rows = result.data if isinstance(result.data, list) else []
    if not rows:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    for row in rows:
        body = Text(display_text(row.get("answer") or ""))
        console.print(_panel(display_text(row.get("question")) or "FAQ", body, border=BLUE))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_venue(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    body = Text()
    if data.get("venue"):
        body.append(display_text(data["venue"]) + "\n")
    if data.get("city"):
        body.append(
            f"{data['city']}  ·  track: {data.get('track') or 'single'}\n", style="ae.accent"
        )
    if data.get("venue_tour_url"):
        body.append("Tour: ", style="ae.meta")
        body.append(str(data["venue_tour_url"]) + "\n", style=BLUE)
    if data.get("accessibility"):
        body.append("\n" + display_text(data["accessibility"]))
    console.print(_panel("Venue", body, border=BLUE))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_sponsors(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    console.print(Text("Sponsors and support", style="ae.title"))
    for row in data.get("sponsors") or []:
        body = Text()
        if row.get("city"):
            body.append(row["city"] + "\n", style="ae.accent")
        if row.get("blurb"):
            body.append(display_text(row["blurb"]) + "\n")
        if row.get("url"):
            body.append(str(row["url"]), style=BLUE)
        console.print(_panel(row.get("name") or "Sponsor", body, border=MAGENTA))
    for row in data.get("support_options") or []:
        body = Text(display_text(row.get("blurb") or ""))
        console.print(_panel(row.get("title") or "Support", body, border=VIOLET))
    if data.get("sponsor_email"):
        console.print(f"[ae.meta]Sponsorship contact:[/] {data['sponsor_email']}")
    if data.get("note"):
        console.print(f"[ae.meta]{display_text(data['note'])}[/]")
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_conduct(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    body = Text(display_text(data.get("summary") or result.answer))
    body.append("\n")
    if data.get("url"):
        body.append("\nRead: ", style="ae.meta")
        body.append(str(data["url"]) + "\n", style=BLUE)
    if data.get("report_email"):
        body.append("Report: ", style="ae.meta")
        body.append(str(data["report_email"]) + "\n", style=BLUE)
    if data.get("terms_url"):
        body.append("Terms: ", style="ae.meta")
        body.append(str(data["terms_url"]), style=BLUE)
    console.print(_panel("Code of conduct", body, border=MAGENTA))


def render_themes(console: Console, result: Result) -> None:
    rows = result.data if isinstance(result.data, list) else []
    if not rows:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    for row in rows:
        body = Text()
        if row.get("command"):
            body.append(f"Website keyword: {row['command']}\n", style="ae.accent")
        body.append(display_text(row.get("description") or ""))
        console.print(_panel(row.get("title") or "Theme", body, border=BLUE))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_live(console: Console, result: Result, *, title: str) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    session = data.get("session")
    if not session:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        nxt = data.get("next")
        if nxt:
            console.print(_panel("Next up", _talk_body(nxt), border=BLUE))
        return
    console.print(_panel(title, _talk_body(session), border=MAGENTA))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_bookmarks(console: Console, result: Result) -> None:
    data = result.data
    if isinstance(data, dict) and "session_ids" in data:
        console.print(f"[ae.ok]{display_text(result.answer)}[/]")
        if data.get("path"):
            console.print(f"[ae.meta]Stored at {data['path']}[/]")
        return
    render_talks(console, result)


def render_agenda(console: Console, result: Result, *, title: str = "Agenda") -> None:
    sessions = result.data if isinstance(result.data, list) else []
    if not sessions:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    table = Table(
        title=title,
        title_style="ae.title",
        border_style=BLUE,
        box=BOX,
        show_header=True,
        pad_edge=False,
        expand=True,
    )
    table.add_column("When", style="ae.accent", no_wrap=True, width=11, min_width=11)
    table.add_column("Session", overflow="fold", ratio=1)
    table.add_column("Kind", style="ae.meta", no_wrap=True, width=8, min_width=6)
    for session in sessions:
        start = _parse_dt(session.get("start"))
        end = _parse_dt(session.get("end"))
        if start and end:
            when = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        elif start:
            when = start.strftime("%H:%M")
        else:
            when = "TBA"
        topics = session.get("topics") or []
        detail = Text(display_text(session.get("title")))
        if topics:
            detail.append("\n" + ", ".join(topics), style="ae.meta")
        table.add_row(when, detail, session.get("kind") or "")
    console.print(table)
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_tickets(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    offers = data.get("current_offers") or []
    published = data.get("published_offers") or []
    body = Text()
    body.append(f"Event: {data.get('event_id') or ''}\n", style="ae.meta")
    state = data.get("state") or ""
    if state:
        body.append("Status: ", style="ae.meta")
        body.append(state + "\n", style=_state_style(state))
    if data.get("registration_url"):
        body.append("Register: ", style="ae.meta")
        body.append(str(data["registration_url"]) + "\n", style=BLUE)
    if data.get("live_availability_verified") is False:
        body.append(
            "Published prices only; confirm live availability on the registration page.\n",
            style="ae.warn",
        )
    console.print(_panel("Tickets", body, border=MAGENTA))

    def offer_table(rows: list[dict], heading: str) -> None:
        if not rows:
            return
        table = Table(
            title=heading,
            title_style="ae.title",
            border_style=MAGENTA,
            box=BOX,
            pad_edge=False,
            expand=True,
        )
        table.add_column("Offer", overflow="fold")
        table.add_column("Price", justify="right", no_wrap=True)
        table.add_column("Valid", overflow="fold")
        table.add_column("Status", no_wrap=True)
        for offer in rows:
            until = _parse_dt(offer.get("valid_until"))
            frm = _parse_dt(offer.get("valid_from"))
            valid = ""
            if frm:
                valid = f"{frm.day} {frm.strftime('%b %Y')}"
            if until:
                valid = (valid + " to " if valid else "until ") + (
                    f"{until.day} {until.strftime('%b %Y')}"
                )
            sold = offer.get("sold_out")
            table.add_row(
                offer.get("name") or "",
                Text(
                    _fmt_money(offer.get("amount", 0), offer.get("currency") or "GBP"),
                    style="ae.price",
                ),
                valid or "-",
                Text("sold out", style="ae.sold") if sold else Text("available", style="ae.ok"),
            )
        console.print(table)

    offer_table(offers, "Current offers")
    if published and published != offers:
        offer_table(published, "All published offers")
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_recordings(console: Console, result: Result) -> None:
    rows = result.data if isinstance(result.data, list) else []
    if not rows:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    console.print(Text("Recordings", style="ae.title"))
    for row in rows:
        body = Text()
        if row.get("event_id"):
            body.append(f"Event: {row['event_id']}\n", style="ae.meta")
        if row.get("url"):
            body.append(str(row["url"]), style=BLUE)
        console.print(_panel(display_text(row.get("title")) or "Recording", body, border=VIOLET))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_search(console: Console, result: Result) -> None:
    rows = result.data if isinstance(result.data, list) else []
    console.print(f"[ae.title]{display_text(result.answer)}[/]")
    if not rows:
        return
    for row in rows:
        excerpt = display_text(row.get("excerpt") or "")
        body = Text(excerpt)
        if row.get("url"):
            body.append("\n")
            body.append(str(row["url"]), style=BLUE)
        console.print(_panel(row.get("source_id") or "match", body, border=VIOLET))


def render_disciplines(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("items") or []
    table = Table(
        title="Disciplines",
        title_style="ae.title",
        border_style=BLUE,
        box=BOX,
        pad_edge=False,
        expand=True,
    )
    table.add_column("ID", style="ae.accent", no_wrap=True)
    table.add_column("Name", overflow="fold")
    table.add_column("Listed", justify="right", no_wrap=True)
    table.add_column("Total", justify="right", no_wrap=True)
    for row in items:
        table.add_row(
            row.get("id") or "",
            row.get("name") or "",
            str(row.get("tool_count", "")),
            str(row.get("total_tool_count", "")),
        )
    console.print(table)
    directory = data.get("directory") or {}
    kinds = data.get("kinds") or []
    summary = Text()
    summary.append(display_text(result.answer) + "\n", style="ae.meta")
    if kinds:
        summary.append("Kinds: " + ", ".join(kinds) + "\n", style="ae.meta")
    if directory:
        summary.append(
            f"Directory {directory.get('version', '')}: "
            f"{directory.get('listing_count', '?')} listings",
            style="ae.meta",
        )
    console.print(summary)


def render_tools(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("items") or []
    console.print(Text("Tools", style="ae.title"))
    for row in items:
        body = Text()
        kind = row.get("kind") or ""
        status = row.get("status") or ""
        body.append(" · ".join(p for p in (kind, status) if p) + "\n", style="ae.accent")
        disciplines = row.get("disciplines") or []
        if disciplines:
            body.append("Disciplines: " + ", ".join(disciplines) + "\n")
        link = row.get("website_url") or row.get("repository_url") or row.get("docs_url")
        if link:
            body.append(str(link) + "\n", style=BLUE)
        body.append(f"id: {row.get('id') or ''}", style="ae.meta")
        console.print(_panel(row.get("name") or row.get("id") or "Tool", body, border=VIOLET))
    meta = Text()
    meta.append(display_text(result.answer) + "\n", style="ae.meta")
    if data.get("next_offset") is not None:
        meta.append(
            f"Next page: repeat with --offset {data['next_offset']}.",
            style="ae.meta",
        )
    console.print(meta)


def render_tool(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    tool = data.get("tool") or {}
    if not tool:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    body = Text()
    body.append(f"{tool.get('kind') or ''}  ·  {tool.get('status') or ''}\n", style="ae.accent")
    disciplines = tool.get("disciplines") or []
    if disciplines:
        body.append("Disciplines: " + ", ".join(disciplines) + "\n")
    categories = tool.get("categories") or []
    if categories:
        body.append("Categories: " + ", ".join(categories) + "\n", style="ae.meta")
    for label, key in (
        ("Website", "website_url"),
        ("Repository", "repository_url"),
        ("Docs", "docs_url"),
    ):
        if tool.get(key):
            body.append(f"{label}: ", style="ae.meta")
            body.append(str(tool[key]) + "\n", style=BLUE)
    aliases = tool.get("aliases") or []
    if aliases:
        body.append("Aliases: " + ", ".join(aliases), style="ae.meta")
    console.print(_panel(tool.get("name") or tool.get("id") or "Tool", body, border=VIOLET))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_discover(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    title = display_text(data.get("conference_name") or data.get("name") or "AgentEng")
    parts: list = []
    description = display_text(data.get("description") or result.answer)
    if description:
        parts.append(Text(description))
    meta = Text()
    cities = data.get("cities") or []
    if cities:
        meta.append("Cities: ", style="ae.meta")
        meta.append(", ".join(cities) + "\n", style="ae.accent")
    if data.get("website"):
        meta.append("Website: ", style="ae.meta")
        meta.append(str(data["website"]) + "\n", style=BLUE)
    tools = data.get("tool_directory") or {}
    if tools:
        meta.append(
            f"Tool directory: {tools.get('listing_count', '?')} listings "
            f"across {tools.get('disciplines', '?')} disciplines\n",
            style="ae.meta",
        )
    questions = data.get("suggested_questions") or []
    if questions:
        meta.append("\nTry asking:\n", style="ae.title")
        for q in questions[:5]:
            meta.append(f"  > {q}\n", style="ae.meta")
    if meta.plain.strip():
        parts.append(meta)
    console.print(_panel(title, Group(*parts), border=BLUE))
    events = data.get("events") or []
    if events:
        fake = Result(
            answer=f"{len(events)} featured event(s).",
            data=events,
            catalogue_version=result.catalogue_version,
            evaluated_at=result.evaluated_at,
            published_at=result.published_at,
            stale=result.stale,
            sources=[],
        )
        render_events(console, fake)


def render_participate(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    body = Text()
    body.append(display_text(result.answer) + "\n\n")
    if data.get("organizer_email"):
        body.append("Email: ", style="ae.meta")
        body.append(str(data["organizer_email"]) + "\n", style=BLUE)
    if data.get("current_event_policy"):
        body.append("\n" + display_text(data["current_event_policy"]) + "\n", style="ae.meta")
    console.print(_panel("Participate", body, border=VIOLET))


def render_proposal(console: Console, result: Result) -> None:
    data = result.data
    console.print(f"[ae.title]{display_text(result.answer)}[/]")
    if isinstance(data, dict) and data:
        table = Table(show_header=False, box=None, pad_edge=False, expand=True)
        table.add_column("Key", style="ae.meta", no_wrap=True)
        table.add_column("Value", overflow="fold")
        for key, value in data.items():
            if key in {"draft"} and isinstance(value, dict):
                continue
            rendered = value
            if isinstance(value, list):
                rendered = ", ".join(str(v) for v in value)
            elif isinstance(value, dict):
                rendered = ", ".join(f"{k}={v}" for k, v in value.items())
            table.add_row(str(key), display_text(str(rendered)))
        console.print(_panel("Proposal", table, border=MAGENTA))
        draft = data.get("draft")
        if isinstance(draft, dict):
            body = Text()
            for key in ("kind", "city", "title", "abstract", "audience", "speaker_name"):
                if draft.get(key):
                    body.append(f"{key}: ", style="ae.meta")
                    body.append(display_text(str(draft[key])) + "\n")
            console.print(_panel("Draft", body, border=VIOLET))


def render_generic(console: Console, result: Result) -> None:
    console.print(f"[ae.title]{display_text(result.answer)}[/]")
    data = result.data
    if not data:
        return
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "title" in data[0]
        and "kind" in data[0]
    ):
        render_agenda(console, result, title="Plan")
        return
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "title" in data[0]
        and "city" in data[0]
    ):
        render_events(console, result)
        return
    console.print_json(data=data)


def render_acp_agents(rows: list[dict], registry: str, console: Console | None = None) -> None:
    """Table for `agenteng code --list`: known ACP agents and whether they are on PATH."""
    console = console or make_console()
    table = Table(
        title="ACP coding agents",
        title_style="ae.title",
        border_style=BLUE,
        box=BOX,
        show_header=True,
        pad_edge=False,
        expand=True,
    )
    table.add_column("Agent", style="ae.accent", no_wrap=True)
    table.add_column("Launch", no_wrap=True)
    table.add_column("Status", ratio=1, overflow="fold")
    for row in rows:
        name = Text(row["name"], style="ae.accent")
        name.append("\n" + display_text(row["title"]), style="ae.meta")
        if row["installed"]:
            status = Text("installed ", style="ae.ok")
            status.append(row["path"], style="ae.meta")
        else:
            status = Text("not found ", style="ae.warn")
            status.append(display_text(row["install"]), style="ae.meta")
        table.add_row(name, Text(row["command"]), status)
    console.print(table)
    installed = sum(1 for row in rows if row["installed"])
    console.print(
        f"[ae.meta]{installed} of {len(rows)} installed. Use `agenteng code --agent NAME PROMPT`, "
        f"or --agent-command for any other ACP agent. Registry: {registry}[/]"
    )


def render_result(result: Result, operation: str, console: Console | None = None) -> None:
    """Render a service Result for humans. Does not change JSON shapes."""
    console = console or make_console()
    if result.status != "ok":
        from .output import empty_but_valid

        if empty_but_valid(result, operation):
            style = "ae.meta"
        elif result.status in {"error", "not_found"}:
            style = "ae.err"
        else:
            style = "ae.warn"
        console.print(Text(display_text(result.answer), style=style))
        if result.data:
            console.print_json(data=result.data)
        _footer(console, result)
        return

    handlers = {
        "events": render_events,
        "event": render_event_detail,
        "speakers": render_speakers,
        "speaker": render_speaker,
        "talks": render_talks,
        "talk": render_talk,
        "faq": render_faq,
        "venue": render_venue,
        "sponsors": render_sponsors,
        "conduct": render_conduct,
        "themes": render_themes,
        "about": render_about,
        "hq": render_hq,
        "bingo": render_bingo,
        "live": lambda c, r: c.print(live_board(r), height=min(c.size.height, 40)),
        "now": lambda c, r: render_live(c, r, title="Now"),
        "next": lambda c, r: render_live(c, r, title="Next"),
        "save": render_bookmarks,
        "unsave": render_bookmarks,
        "my_agenda": render_bookmarks,
        "agenda": render_agenda,
        "plan": lambda c, r: render_agenda(c, r, title="Plan"),
        "tickets": render_tickets,
        "recordings": render_recordings,
        "search": render_search,
        "ask": render_search if isinstance(result.data, list) else render_generic,
        "disciplines": render_disciplines,
        "tools": render_tools,
        "tool": render_tool,
        "discover": render_discover,
        "participate": render_participate,
        "proposal_draft": render_proposal,
        "proposal_preview": render_proposal,
        "proposal_export": render_proposal,
        "proposal_prepare": render_proposal,
        "proposal_submit": render_proposal,
        "proposal_status": render_proposal,
        "proposal_withdraw": render_proposal,
    }
    handler = handlers.get(operation, render_generic)
    handler(console, result)
    _footer(console, result)


# --- about / hq -------------------------------------------------------------


def _kv_table() -> Table:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="ae.accent", no_wrap=True)
    table.add_column(overflow="fold")
    return table


def render_about(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    section = data.get("section")
    if not section:
        intro = Text()
        if data.get("summary"):
            intro.append(display_text(data["summary"]) + "\n\n")
        if data.get("definition"):
            intro.append("Our definition  ", style="ae.accent")
            intro.append(display_text(data["definition"]))
        console.print(_panel(data.get("name") or "Agent Engineering HQ", intro, border=MAGENTA))
    organiser = data.get("organiser")
    if organiser:
        body = Text()
        body.append(display_text(organiser["name"]), style="bold")
        if organiser.get("blurb"):
            body.append("\n" + display_text(organiser["blurb"]))
        body.append("\n" + organiser["url"], style="ae.blue")
        console.print(_panel("Organised by", body, border=VIOLET))
    chair = data.get("chair")
    if chair:
        body = Text()
        body.append(display_text(chair["name"]), style="bold")
        body.append("\n" + display_text(chair["title"]), style="ae.meta")
        if chair.get("bio"):
            body.append("\n\n" + display_text(chair["bio"]))
        for link in chair.get("links") or []:
            body.append(f"\n{link['label']}: ", style="ae.accent")
            body.append(link["url"], style="ae.blue")
        console.print(_panel("Conference chair", body, border=VIOLET))
    links = data.get("links")
    if links:
        table = _kv_table()
        labels = {
            "website": "Website",
            "hq": "Agent Engineering HQ",
            "london": "London",
            "san_francisco": "San Francisco",
            "code_of_conduct": "Code of conduct",
        }
        for key, url in links.items():
            table.add_row(labels.get(key, key), url)
        if data.get("contact_email"):
            table.add_row("Contact", data["contact_email"])
        console.print(_panel("Links", table))
    connect = data.get("connect")
    if connect:
        table = _kv_table()
        table.add_row("Install", connect["install"])
        table.add_row("Or with uv", connect["install_uv"])
        table.add_row("Remote MCP", connect["mcp_url"])
        table.add_row("A2A agent card", connect["agent_card_url"])
        table.add_row("HTTP query", "POST " + connect["http_query_url"])
        table.add_row("Local MCP", connect["local_mcp"])
        table.add_row("Set up a client", " | ".join(connect["connect_commands"]))
        console.print(_panel("Connect your agent", table, border=BLUE))


def render_hq(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    if not data.get("section") and data.get("summary"):
        intro = Text(display_text(data["summary"]))
        if data.get("cities"):
            intro.append("\n\n" + display_text(data["cities"]), style="ae.meta")
        intro.append("\n" + str(data.get("url") or ""), style="ae.blue")
        console.print(_panel("Agent Engineering HQ", intro, border=MAGENTA))
    if data.get("manifesto"):
        body = Table.grid(padding=(0, 2))
        body.add_column(style="ae.meta", no_wrap=True)
        body.add_column(overflow="fold")
        for i, paragraph in enumerate(data["manifesto"], 1):
            style = "bold" if i == 1 else ""
            body.add_row(f"{i:02d}", Text(display_text(paragraph), style=style))
            if i < len(data["manifesto"]):
                body.add_row("", "")
        console.print(_panel("The Agent Engineering Manifesto", body, border=VIOLET))
    if data.get("mindset"):
        table = Table(box=BOX, border_style=BLUE, expand=True, show_header=False)
        table.add_column(style="ae.title", overflow="fold", ratio=2)
        table.add_column(overflow="fold", ratio=5)
        for principle in data["mindset"]:
            table.add_row(display_text(principle["title"]), display_text(principle["description"]))
        console.print(_panel("The Agent Engineering Mindset", table, border=BLUE))
    if data.get("further_reading"):
        body = Table.grid(padding=(0, 2))
        body.add_column(style="ae.meta", no_wrap=True)
        body.add_column(overflow="fold")
        if data.get("further_reading_intro"):
            body.add_row("", Text(display_text(data["further_reading_intro"]), style="italic"))
        for item in data["further_reading"]:
            text = Text(display_text(item["title"]), style="bold")
            text.append("\n" + item["url"], style="ae.blue")
            body.add_row(item["date"], text)
        console.print(_panel("Further reading", body, border=VIOLET))


# --- talk bingo ---------------------------------------------------------------


def bingo_table(card: dict, marked: set[tuple[int, int]] | None = None) -> Table:
    marked = marked or set()
    size = card["size"]
    table = Table(
        box=box.HEAVY,
        border_style=VIOLET,
        show_lines=True,
        expand=False,
        title=Text("AGENTENG TALK BINGO", style=f"bold {MAGENTA}"),
        caption=Text(f"Card {card['card_id']}", style="ae.meta"),
        pad_edge=True,
    )
    table.add_column("", style="ae.meta", no_wrap=True, justify="right")
    for c in range(size):
        table.add_column("ABCDE"[c], justify="center", vertical="middle", width=14)
    for r, row in enumerate(card["grid"]):
        cells = []
        for c, label in enumerate(row):
            if label == "FREE":
                cells.append(Text("\n★ FREE ★\n", style=f"bold white on {MAGENTA}"))
            elif (r, c) in marked:
                cells.append(Text(f"\n✓ {display_text(label)}\n", style=f"bold white on {VIOLET}"))
            else:
                cells.append(Text(f"\n{display_text(label)}\n", style="bold"))
        table.add_row(f"\n{r + 1}", *cells)
    return table


def render_bingo(console: Console, result: Result) -> None:
    card = result.data if isinstance(result.data, dict) else {}
    if not card.get("grid"):
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    console.print(Text(display_text(card["event_title"]), style="ae.title"))
    console.print(bingo_table(card))
    console.print(f"[ae.meta]{display_text(card['rules'])}[/]")
    console.print(f"[ae.accent]Same card again:[/] {card['command']}")
    console.print("[ae.accent]Print it:[/] add --format html --output bingo.html")


def play_bingo(result: Result, console: Console | None = None, *, ask=None) -> set[str]:
    """Mark squares in the terminal. Returns the winning lines seen. Nothing is stored."""
    import click

    from .screens import winning_lines

    console = console or make_console()
    card = result.data
    size = card["size"]
    marked = {
        (r, c) for r, row in enumerate(card["grid"]) for c, v in enumerate(row) if v == "FREE"
    }
    ask = ask or (lambda: click.prompt("Mark a square (B3), u = undo, q = quit", default="q"))
    history: list[tuple[int, int]] = []
    won: set[str] = set()
    while True:
        console.print(bingo_table(card, marked))
        try:
            answer = str(ask()).strip().upper()
        except (EOFError, KeyboardInterrupt, click.Abort):
            answer = "Q"
        if answer in {"Q", "QUIT", ""}:
            console.print("[ae.meta]Card not saved; re-create it any time:[/] " + card["command"])
            return won
        if answer == "U":
            if history:
                marked.discard(history.pop())
            continue
        if len(answer) < 2 or answer[0] not in "ABCDE"[:size] or not answer[1:].isdigit():
            console.print("[ae.warn]Use a column letter and row number, such as B3.[/]")
            continue
        r, c = int(answer[1:]) - 1, "ABCDE".index(answer[0])
        if not 0 <= r < size:
            console.print(f"[ae.warn]Rows run from 1 to {size}.[/]")
            continue
        if (r, c) in marked and card["grid"][r][c] != "FREE":
            marked.discard((r, c))
        else:
            marked.add((r, c))
            history.append((r, c))
        new = set(winning_lines(marked, size)) - won
        if new:
            won |= new
            console.print(
                Panel(
                    Text(
                        f"BINGO! {', '.join(sorted(new))}",
                        style=f"bold white on {MAGENTA}",
                        justify="center",
                    ),
                    border_style=MAGENTA,
                )
            )


# --- live venue screen --------------------------------------------------------

_DIGITS = {
    "0": ["███", "█ █", "█ █", "█ █", "███"],
    "1": [" ██", "  █", "  █", "  █", "  █"],
    "2": ["███", "  █", "███", "█  ", "███"],
    "3": ["███", "  █", "███", "  █", "███"],
    "4": ["█ █", "█ █", "███", "  █", "  █"],
    "5": ["███", "█  ", "███", "  █", "███"],
    "6": ["███", "█  ", "███", "█ █", "███"],
    "7": ["███", "  █", "  █", "  █", "  █"],
    "8": ["███", "█ █", "███", "█ █", "███"],
    "9": ["███", "█ █", "███", "  █", "███"],
    ":": [" ", "▪", " ", "▪", " "],
}


def big_clock(value: str, style: str = MAGENTA) -> Text:
    rows = [" ".join(_DIGITS[ch][i] for ch in value if ch in _DIGITS) for i in range(5)]
    return Text("\n".join(rows), style=f"bold {style}", no_wrap=True)


def _hhmm(value: str | None) -> str:
    parsed = _parse_dt(value)
    return parsed.strftime("%H:%M") if parsed else ""


def _minutes(seconds: int | None) -> str:
    if seconds is None:
        return ""
    minutes = max(0, round(seconds / 60))
    if minutes >= 60:
        return f"{minutes // 60} h {minutes % 60:02d} min"
    return f"{minutes} min"


def _talk_lines(talk: dict, *, title_style: str) -> Text:
    text = Text()
    text.append(display_text(talk.get("talk_title") or talk.get("title")), style=title_style)
    who = [talk.get("speaker_name"), talk.get("speaker_company")]
    who = " · ".join(display_text(w) for w in who if w)
    if who:
        text.append("\n" + who, style=f"bold {BLUE}")
    if talk.get("speaker_role"):
        text.append("\n" + display_text(talk["speaker_role"]), style="ae.meta")
    return text


def live_board(result: Result):
    """One full-screen frame for `agenteng live`."""
    from rich.layout import Layout
    from rich.progress_bar import ProgressBar

    data = result.data if isinstance(result.data, dict) else {}
    event = data.get("event") or {}
    as_of = _parse_dt(data.get("as_of"))
    clock = as_of.strftime("%H:%M") if as_of else "--:--"

    header = Table.grid(expand=True)
    header.add_column(ratio=1, vertical="middle")
    header.add_column(justify="right", vertical="middle")
    head = Text()
    head.append(display_text(event.get("title") or "AgentEng").upper(), style=f"bold {MAGENTA}")
    place = [event.get("venue")]
    if event.get("track"):
        place.append(f"{str(event['track']).capitalize()} track")
    head.append("\n" + " · ".join(display_text(p) for p in place if p), style="ae.meta")
    if as_of:
        head.append("\n" + as_of.strftime("%A %-d %B %Y"), style="ae.accent")
    header.add_row(head, big_clock(clock))

    current, upcoming, phase = data.get("current"), data.get("next"), data.get("phase")
    if current:
        body = Table.grid(expand=True)
        body.add_column()
        body.add_row(_talk_lines(current, title_style="bold white"))
        body.add_row("")
        span = f"{_hhmm(current.get('start'))} to {_hhmm(current.get('end'))}"
        body.add_row(
            Text(f"{span}  ·  {_minutes(current.get('remaining_seconds'))} left", style="ae.accent")
        )
        body.add_row(
            ProgressBar(total=1.0, completed=current.get("progress") or 0, complete_style=MAGENTA)
        )
        now_panel = Panel(
            body,
            title=Text(" NOW ", style=f"bold white on {MAGENTA}"),
            title_align="left",
            border_style=MAGENTA,
            padding=(1, 2),
        )
    else:
        message = {
            "before": "Doors open soon.",
            "between": "Break. Grab a coffee and say hello.",
            "after": "That's a wrap. Thank you for coming.",
        }.get(phase, display_text(result.answer))
        now_panel = Panel(
            Text(message, style="bold white", justify="center"),
            title=Text(" NOW ", style=f"bold white on {MAGENTA}"),
            title_align="left",
            border_style=MAGENTA,
            padding=(1, 2),
        )
    if upcoming:
        nxt = _talk_lines(upcoming, title_style="bold")
        nxt.append(
            f"\n{_hhmm(upcoming.get('start'))}  ·  in {_minutes(upcoming.get('starts_in_seconds'))}",
            style="ae.accent",
        )
    else:
        nxt = Text("Nothing else on the published agenda today.", style="ae.meta")
    next_panel = Panel(
        nxt,
        title=Text(" NEXT UP ", style=f"bold white on {BLUE}"),
        title_align="left",
        border_style=BLUE,
        padding=(1, 2),
    )
    later = Table.grid(padding=(0, 2))
    later.add_column(style="ae.accent", no_wrap=True)
    later.add_column(overflow="ellipsis")
    for row in data.get("later") or []:
        later.add_row(_hhmm(row.get("start")), display_text(row.get("title")))
    later_panel = Panel(
        later,
        title=Text(" LATER ", style=f"bold white on {VIOLET}"),
        title_align="left",
        border_style=VIOLET,
        padding=(0, 2),
    )
    footer = Text(
        "agentengineering.world  ·  agenteng live  ·  Ctrl-C to exit",
        style="ae.meta",
        justify="center",
    )

    layout = Layout()
    layout.split_column(
        Layout(Panel(header, border_style=VIOLET, padding=(0, 2)), name="head", size=9),
        Layout(now_panel, name="now", ratio=3),
        Layout(name="bottom", ratio=2),
        Layout(footer, name="foot", size=1),
    )
    layout["bottom"].split_row(Layout(next_panel, ratio=3), Layout(later_panel, ratio=2))
    return layout


def run_live_screen(ctx, payload: dict, *, refresh: int, once: bool = False, console=None) -> None:
    """Redraw the venue board every `refresh` seconds until Ctrl-C."""
    import time
    from datetime import datetime, timedelta

    from rich.live import Live

    from .cli import execute
    from .models import Request

    console = console or make_console()
    started = time.monotonic()
    start_at = payload.get("at")

    def frame():
        request = dict(payload)
        if start_at:
            # A demo --at clock keeps running forward from the given time.
            moved = datetime.fromisoformat(start_at) + timedelta(seconds=time.monotonic() - started)
            request["at"] = moved.isoformat()
        result = execute(ctx, Request.model_validate(request))
        if result.status != "ok" and not (
            isinstance(result.data, dict) and result.data.get("event")
        ):
            raise ValueError(result.answer)
        return live_board(result)

    if once:
        console.print(frame(), height=console.size.height)
        return
    try:
        with Live(frame(), console=console, screen=True, refresh_per_second=4) as live:
            while True:
                time.sleep(refresh)
                live.update(frame())
    except KeyboardInterrupt:
        pass
