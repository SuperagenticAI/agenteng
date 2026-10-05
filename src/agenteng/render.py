"""Rich human-readable renderers for AgentEng CLI results."""

from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Result
from .output import BLUE, MAGENTA, VIOLET, display_text, make_console


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_date(event: dict) -> str:
    precision = event.get("date_precision") or "day"
    date = event.get("date") or ""
    if precision == "month" and len(date) >= 7:
        return date[:7]
    return date


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
    for source in result.sources:
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
        padding=(0, 1),
    )


def render_events(console: Console, result: Result) -> None:
    events = result.data if isinstance(result.data, list) else []
    if not events:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    table = Table(
        title="Events",
        title_style="ae.title",
        border_style=VIOLET,
        show_lines=False,
        pad_edge=False,
    )
    table.add_column("Title", style="bold")
    table.add_column("City")
    table.add_column("Date")
    table.add_column("Venue", overflow="fold")
    table.add_column("Status")
    table.add_column("From", justify="right")
    for event in events:
        offer = _cheapest_offer(event.get("offers"))
        price = _fmt_money(offer["amount"], offer.get("currency") or "GBP") if offer else "-"
        state = event.get("state") or ("cancelled" if event.get("cancelled") else "")
        table.add_row(
            display_text(event.get("title")),
            event.get("city") or "",
            _fmt_date(event),
            display_text(event.get("venue")),
            Text(state, style=_state_style(state)),
            Text(price, style="ae.price" if offer else "ae.meta"),
        )
    console.print(table)
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_event_detail(console: Console, result: Result) -> None:
    events = result.data if isinstance(result.data, list) else []
    if not events:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    event = events[0]
    lines = Text()
    lines.append(display_text(event.get("title")) + "\n", style="bold")
    lines.append(f"{event.get('city') or ''}  ·  {_fmt_date(event)}\n", style="ae.accent")
    if event.get("venue"):
        lines.append(display_text(event["venue"]) + "\n")
    state = event.get("state") or ""
    if state:
        lines.append("Status: ", style="ae.meta")
        lines.append(state + "\n", style=_state_style(state))
    if event.get("registration_url"):
        lines.append("Register: ", style="ae.meta")
        lines.append(str(event["registration_url"]) + "\n", style=BLUE)
    if event.get("recording_url"):
        lines.append("Recording: ", style="ae.meta")
        lines.append(str(event["recording_url"]) + "\n", style=BLUE)
    offer = _cheapest_offer(event.get("offers"))
    if offer:
        lines.append("Tickets from ", style="ae.meta")
        lines.append(
            _fmt_money(offer["amount"], offer.get("currency") or "GBP"),
            style="ae.price",
        )
        lines.append(f" ({offer.get('name')})\n", style="ae.meta")
    lines.append(f"\nid: {event.get('id')}", style="ae.meta")
    console.print(_panel("Event", lines, border=BLUE))
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_speakers(console: Console, result: Result) -> None:
    speakers = result.data if isinstance(result.data, list) else []
    if not speakers:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    for speaker in speakers:
        body = Text()
        role = speaker.get("role") or ""
        company = speaker.get("company") or ""
        meta = " · ".join(p for p in (role, company) if p)
        if meta:
            body.append(meta + "\n", style="ae.accent")
        talk = speaker.get("talk_title")
        if talk:
            body.append("Talk: ", style="ae.meta")
            body.append(display_text(talk) + "\n")
        events = speaker.get("event_ids") or []
        if events:
            body.append("Events: " + ", ".join(events), style="ae.meta")
        console.print(
            _panel(speaker.get("name") or speaker.get("id") or "Speaker", body, border=VIOLET)
        )
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_agenda(console: Console, result: Result, *, title: str = "Agenda") -> None:
    sessions = result.data if isinstance(result.data, list) else []
    if not sessions:
        console.print(f"[ae.meta]{display_text(result.answer)}[/]")
        return
    table = Table(
        title=title,
        title_style="ae.title",
        border_style=BLUE,
        show_header=True,
        pad_edge=False,
    )
    table.add_column("When", style="ae.accent", no_wrap=True)
    table.add_column("Session")
    table.add_column("Kind", style="ae.meta")
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
        detail = display_text(session.get("title"))
        if topics:
            detail += f"\n[ae.meta]{', '.join(topics)}[/]"
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
        table = Table(title=heading, title_style="ae.title", border_style=MAGENTA, pad_edge=False)
        table.add_column("Offer")
        table.add_column("Price", justify="right")
        table.add_column("Valid")
        table.add_column("Status")
        for offer in rows:
            until = _parse_dt(offer.get("valid_until"))
            frm = _parse_dt(offer.get("valid_from"))
            valid = ""
            if frm:
                valid = frm.date().isoformat()
            if until:
                valid = (valid + " to " if valid else "until ") + until.date().isoformat()
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
    table = Table(title="Recordings", title_style="ae.title", border_style=VIOLET, pad_edge=False)
    table.add_column("Title")
    table.add_column("Event id", style="ae.meta")
    table.add_column("URL", overflow="fold", style=BLUE)
    for row in rows:
        table.add_row(
            display_text(row.get("title")), row.get("event_id") or "", str(row.get("url") or "")
        )
    console.print(table)
    console.print(f"[ae.meta]{display_text(result.answer)}[/]")


def render_search(console: Console, result: Result) -> None:
    rows = result.data if isinstance(result.data, list) else []
    console.print(f"[ae.title]{display_text(result.answer)}[/]")
    if not rows:
        return
    for row in rows:
        excerpt = display_text(row.get("excerpt") or "")
        if len(excerpt) > 400:
            excerpt = excerpt[:397] + "..."
        body = Text()
        body.append(excerpt + "\n")
        if row.get("url"):
            body.append(str(row["url"]), style=BLUE)
        console.print(_panel(row.get("source_id") or "match", body, border=VIOLET))


def render_disciplines(console: Console, result: Result) -> None:
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("items") or []
    table = Table(
        title="Disciplines",
        title_style="ae.title",
        border_style=BLUE,
        pad_edge=False,
    )
    table.add_column("ID", style="ae.accent")
    table.add_column("Name")
    table.add_column("Listed", justify="right")
    table.add_column("Total", justify="right")
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
    table = Table(title="Tools", title_style="ae.title", border_style=VIOLET, pad_edge=False)
    table.add_column("ID", style="ae.accent", no_wrap=True)
    table.add_column("Name")
    table.add_column("Kind", style="ae.meta")
    table.add_column("Disciplines", overflow="fold")
    for row in items:
        table.add_row(
            row.get("id") or "",
            row.get("name") or "",
            row.get("kind") or "",
            ", ".join(row.get("disciplines") or []),
        )
    console.print(table)
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
    body = Text()
    body.append(display_text(data.get("description") or result.answer) + "\n\n")
    cities = data.get("cities") or []
    if cities:
        body.append("Cities: ", style="ae.meta")
        body.append(", ".join(cities) + "\n", style="ae.accent")
    if data.get("website"):
        body.append("Website: ", style="ae.meta")
        body.append(str(data["website"]) + "\n", style=BLUE)
    tools = data.get("tool_directory") or {}
    if tools:
        body.append(
            f"Tool directory: {tools.get('listing_count', '?')} listings "
            f"across {tools.get('disciplines', '?')} disciplines\n",
            style="ae.meta",
        )
    questions = data.get("suggested_questions") or []
    if questions:
        body.append("\nTry asking:\n", style="ae.title")
        for q in questions[:5]:
            body.append(f"  · {q}\n", style="ae.meta")
    console.print(_panel(title, body, border=BLUE))
    events = data.get("events") or []
    if events:
        # Reuse event table shape via a temporary Result-like path.
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
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_column("Key", style="ae.meta")
        table.add_column("Value")
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


def render_result(result: Result, operation: str, console: Console | None = None) -> None:
    """Render a service Result for humans. Does not change JSON shapes."""
    console = console or make_console()
    if result.status != "ok":
        style = "ae.err" if result.status in {"error", "not_found"} else "ae.warn"
        console.print(Text(display_text(result.answer), style=style))
        if result.data:
            console.print_json(data=result.data)
        _footer(console, result)
        return

    handlers = {
        "events": render_events,
        "event": render_event_detail,
        "speakers": render_speakers,
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
