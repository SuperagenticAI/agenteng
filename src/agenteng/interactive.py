"""Interactive terminal menu for ae / agenteng with no arguments.

Uses questionary for arrow-key selection. Rich prompts alone only support
typed input; questionary stays small and gives a clear keyboard UI.
"""

from __future__ import annotations

import webbrowser

import click
import questionary
from questionary import Choice, Style

from .discovery import connection
from .output import BLUE, MAGENTA, VIOLET, display_text, stdin_is_tty, stdout_is_tty

AE_STYLE = Style(
    [
        ("qmark", f"fg:{BLUE} bold"),
        ("question", "bold"),
        ("answer", f"fg:{VIOLET} bold"),
        ("pointer", f"fg:{MAGENTA} bold"),
        ("highlighted", f"fg:{MAGENTA} bold"),
        ("selected", f"fg:{BLUE}"),
        ("instruction", "italic"),
    ]
)


def _select(message: str, choices: list[Choice | str], *, default=None):
    if not choices:
        return None
    try:
        return questionary.select(
            message,
            choices=choices,
            style=AE_STYLE,
            default=default,
            instruction="(use arrow keys, enter to confirm, ctrl-c to quit)",
        ).ask()
    except KeyboardInterrupt:
        return None


def _text(message: str, default: str = "") -> str | None:
    try:
        return questionary.text(message, default=default, style=AE_STYLE).ask()
    except KeyboardInterrupt:
        return None


def list_events(ctx) -> list[dict]:
    from .cli import dispatch

    result = dispatch(ctx, dict(operation="events"), quiet=True)
    rows = result.data if isinstance(result.data, list) else []
    return rows


def pick_event_id(ctx, *, prompt: str = "Pick an event") -> str | None:
    rows = list_events(ctx)
    if not rows:
        click.echo("No events in the catalogue.", err=True)
        return None
    choices = [
        Choice(
            title=f"{display_text(e.get('title'))}  ·  {e.get('city')}  ·  "
            f"{e.get('date')}  [{e.get('state') or ''}]",
            value=e.get("id"),
        )
        for e in rows
        if e.get("id")
    ]
    return _select(prompt, choices)


def require_event_id(ctx, event_id: str | None) -> str:
    """Resolve an optional event_id; offer a picker on a TTY."""
    if event_id:
        return event_id
    if stdout_is_tty() and stdin_is_tty():
        picked = pick_event_id(ctx)
        if not picked:
            raise click.Abort()
        return picked
    raise click.ClickException(
        "event_id is required. Pass it as an argument, or run in a terminal to pick one."
    )


def _show(ctx, payload: dict) -> None:
    from .cli import dispatch

    dispatch(ctx, payload)


def _event_submenu(ctx, event_id: str) -> None:
    while True:
        action = _select(
            f"Event: {event_id}",
            [
                Choice("Overview", "overview"),
                Choice("Speakers", "speakers"),
                Choice("Agenda", "agenda"),
                Choice("Tickets", "tickets"),
                Choice("Recordings", "recordings"),
                Choice("Open registration link", "register"),
                Choice("Back", "back"),
            ],
        )
        if action in {None, "back"}:
            return
        if action == "overview":
            _show(ctx, dict(operation="event", event_id=event_id))
        elif action == "speakers":
            _show(ctx, dict(operation="speakers", event_id=event_id))
        elif action == "agenda":
            _show(ctx, dict(operation="agenda", event_id=event_id))
        elif action == "tickets":
            _show(ctx, dict(operation="tickets", event_id=event_id))
        elif action == "recordings":
            _show(ctx, dict(operation="recordings", event_id=event_id))
        elif action == "register":
            from .cli import dispatch

            result = dispatch(ctx, dict(operation="tickets", event_id=event_id), quiet=True)
            data = result.data if isinstance(result.data, dict) else {}
            url = data.get("registration_url")
            if not url:
                click.echo("No registration link published for this event.", err=True)
            else:
                click.echo(f"Opening {url}")
                try:
                    webbrowser.open(str(url))
                except Exception:
                    click.echo(str(url))


def _browse_tools(ctx) -> None:
    from .cli import dispatch

    result = dispatch(ctx, dict(operation="disciplines"), quiet=True)
    data = result.data if isinstance(result.data, dict) else {}
    items = data.get("items") or []
    choices = [
        Choice(f"{row.get('name')} ({row.get('tool_count')} listings)", row.get("id"))
        for row in items
        if row.get("id")
    ]
    choices.append(Choice("Back", None))
    discipline = _select("Browse tools by discipline", choices)
    if not discipline:
        return
    _show(ctx, dict(operation="tools", discipline=discipline, limit=20, offset=0))


def _draft_proposal(ctx) -> None:
    city = _select("City", [Choice("London", "London"), Choice("San Francisco", "San Francisco")])
    if not city:
        return
    kind = _select(
        "What are you drafting?",
        [
            Choice("Talk", "talk"),
            Choice("Workshop", "workshop"),
            Choice("Event idea", "event_idea"),
            Choice("Feedback", "feedback"),
        ],
        default="event_idea",
    )
    if not kind:
        return
    title = _text("Working title")
    if title is None:
        return
    abstract = _text("Short abstract or idea")
    if abstract is None:
        return
    audience = _text("Intended audience")
    if audience is None:
        return
    speaker_name = ""
    outcomes: list[str] = []
    if kind in {"talk", "workshop"}:
        speaker_name = _text("Speaker name") or ""
        outcome = _text("One practical learning outcome") or ""
        if outcome:
            outcomes = [outcome]
    _show(
        ctx,
        {
            "operation": "proposal_draft",
            "draft": {
                "kind": kind,
                "city": city,
                "title": title or "",
                "abstract": abstract or "",
                "audience": audience or "",
                "outcomes": outcomes,
                "speaker_name": speaker_name,
                "contact_email": "",
                "event_id": None,
                "future_event": True,
            },
        },
    )


def _connect_agent(ctx) -> None:
    client = _select(
        "Coding agent",
        [
            Choice("Cursor", "cursor"),
            Choice("Claude Code", "claude-code"),
            Choice("Codex", "codex"),
            Choice("Generic MCP", "generic"),
        ],
    )
    if not client:
        return
    try:
        from .config import Settings

        click.echo(connection(client, "stdio", Settings.public_url))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def run_menu(ctx) -> None:
    """Top-level interactive loop. Ctrl-C or Quit exits cleanly."""
    click.echo("AgentEng interactive mode. Pick an option or press ctrl-c to quit.\n")
    while True:
        try:
            action = _select(
                "What would you like to do?",
                [
                    Choice("Browse events", "events"),
                    Choice("Search the catalogue", "search"),
                    Choice("Browse the tool directory", "tools"),
                    Choice("Draft a talk or event idea", "draft"),
                    Choice("Connect a coding agent", "connect"),
                    Choice("Discover (welcome)", "discover"),
                    Choice("Quit", "quit"),
                ],
            )
        except KeyboardInterrupt:
            click.echo("\nBye.")
            return
        if action in {None, "quit"}:
            click.echo("Bye.")
            return
        try:
            if action == "events":
                event_id = pick_event_id(ctx)
                if event_id:
                    _event_submenu(ctx, event_id)
            elif action == "search":
                query = _text("Search query")
                if query:
                    _show(ctx, dict(operation="search", query=query))
            elif action == "tools":
                _browse_tools(ctx)
            elif action == "draft":
                _draft_proposal(ctx)
            elif action == "connect":
                _connect_agent(ctx)
            elif action == "discover":
                _show(ctx, dict(operation="discover"))
        except click.Abort:
            click.echo("\nBye.")
            return
        except KeyboardInterrupt:
            click.echo("\nBye.")
            return
        except click.ClickException as exc:
            click.echo(str(exc), err=True)
