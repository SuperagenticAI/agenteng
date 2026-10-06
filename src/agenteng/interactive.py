"""Interactive terminal menu for ae / agenteng with no arguments.

Uses questionary for arrow-key selection. Rich prompts alone only support
typed input; questionary stays small and gives a clear keyboard UI.
"""

from __future__ import annotations

import webbrowser

import click
import questionary
import questionary.prompts.common as qcommon
from questionary import Choice, Style

from .discovery import connection
from .output import BLUE, MAGENTA, VIOLET, stdin_is_tty, stdout_is_tty
from .render import event_label

# Prefer a plain ASCII pointer so every terminal font can render it.
qcommon.DEFAULT_SELECTED_POINTER = ">"

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
            instruction="(arrows, enter, ctrl-c to quit)",
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
    choices = [Choice(title=event_label(e), value=e.get("id")) for e in rows if e.get("id")]
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


def _event_submenu(ctx, event: dict) -> None:
    event_id = event.get("id") or ""
    header = event_label(event)
    while True:
        action = _select(
            header,
            [
                Choice("Overview", "overview"),
                Choice("Speakers", "speakers"),
                Choice("Talks and abstracts", "talks"),
                Choice("Agenda", "agenda"),
                Choice("What's on now / next", "live"),
                Choice("Venue", "venue"),
                Choice("FAQ", "faq"),
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
        elif action == "talks":
            _show(ctx, dict(operation="talks", event_id=event_id))
        elif action == "agenda":
            _show(ctx, dict(operation="agenda", event_id=event_id))
        elif action == "live":
            _show(ctx, dict(operation="now", event_id=event_id))
            _show(ctx, dict(operation="next", event_id=event_id))
        elif action == "venue":
            _show(ctx, dict(operation="venue", event_id=event_id))
        elif action == "faq":
            _show(ctx, dict(operation="faq", event_id=event_id))
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


def pick_talk_id(ctx) -> str | None:
    """Pick an event, then one of its talks. None when the user backs out."""
    from .cli import dispatch

    while True:
        event_id = pick_event_id(ctx, prompt="Talks from which event?")
        if not event_id:
            return None
        try:
            result = dispatch(
                ctx, dict(operation="talks", event_id=event_id, limit=100), quiet=True
            )
            rows = result.data if isinstance(result.data, list) else []
        except click.exceptions.Exit:
            rows = []
        if not rows:
            click.echo("That event has no published talks yet. Pick another.", err=True)
            continue
        choices = [
            Choice(f"{row.get('title')} ({row.get('speaker_name') or 'TBA'})", row.get("id"))
            for row in rows
            if row.get("id")
        ]
        choices.append(Choice("Back", None))
        talk_id = _select("Pick a talk", choices)
        if talk_id:
            return talk_id


def _code_with_agent(ctx) -> None:
    """Pick an installed ACP agent, optionally a talk, then chat (ae code)."""
    from .acp_agents import AGENTS, REGISTRY_URL, installed_agents
    from .render import render_acp_agents

    found = installed_agents()
    if not found:
        render_acp_agents([spec.as_dict() for spec in AGENTS], REGISTRY_URL)
        click.echo(
            "No ACP coding agent is on PATH yet. Install one of the agents above, "
            "then pick this option again.",
            err=True,
        )
        return
    choices = [Choice(f"{spec.title} ({spec.binary})", spec) for spec in found]
    choices.append(Choice("Back", None))
    spec = _select("Code with which agent?", choices)
    if spec is None:
        return
    context = _select(
        "Add a talk as context?",
        [Choice("No, just chat", "none"), Choice("Pick a talk", "talk"), Choice("Back", None)],
    )
    if context is None:
        return
    context_ids: list[str] = []
    if context == "talk":
        talk_id = pick_talk_id(ctx)
        if not talk_id:
            return
        context_ids.append(talk_id)
    from .cli import run_code

    try:
        argv = spec.argv()
    except LookupError as exc:
        raise click.ClickException(str(exc)) from exc
    run_code(ctx, argv, "", chat=True, context_ids=context_ids)


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
                    Choice("FAQ / code of conduct", "faq"),
                    Choice("Sponsors and support", "sponsors"),
                    Choice("Program themes", "themes"),
                    Choice("My bookmarked agenda", "my_agenda"),
                    Choice("Browse the tool directory", "tools"),
                    Choice("Draft a talk or event idea", "draft"),
                    Choice("Code with an agent (ACP, experimental)", "code"),
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
                rows = list_events(ctx)
                if not rows:
                    click.echo("No events in the catalogue.", err=True)
                    continue
                choices = [Choice(title=event_label(e), value=e) for e in rows if e.get("id")]
                picked = _select("Pick an event", choices)
                if picked:
                    _event_submenu(ctx, picked)
            elif action == "search":
                query = _text("Search query")
                if query:
                    _show(ctx, dict(operation="search", query=query))
            elif action == "faq":
                _show(ctx, dict(operation="faq"))
                _show(ctx, dict(operation="conduct"))
            elif action == "sponsors":
                _show(ctx, dict(operation="sponsors"))
            elif action == "themes":
                _show(ctx, dict(operation="themes"))
            elif action == "my_agenda":
                _show(ctx, dict(operation="my_agenda"))
            elif action == "tools":
                _browse_tools(ctx)
            elif action == "draft":
                _draft_proposal(ctx)
            elif action == "code":
                _code_with_agent(ctx)
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
