"""Public event CLI. Optional protocol and model dependencies load on demand."""

import asyncio
import json
import os
from pathlib import Path
from typing import get_args

import click
import httpx
from pydantic import ValidationError

from . import __version__
from .config import Settings
from .discovery import connection, validate_origin
from .models import Request, Result, canonical_city
from .output import empty_but_valid, stdin_is_tty, stdout_is_tty
from .service import Service
from .tool_directory import DISCIPLINES, ToolKind


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__)
@click.option(
    "--catalogue", type=click.Path(exists=True, dir_okay=False), help="Local public catalogue JSON."
)
@click.option("--remote", help="HTTP service base URL (otherwise use bundled offline catalogue).")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the shared structured Result JSON (also used when stdout is not a TTY).",
)
@click.option("--list-disciplines", "site_shortcut", flag_value="disciplines", hidden=True)
@click.option("--themes", "site_shortcut", flag_value="themes", hidden=True)
@click.option("--list-cities", "site_shortcut", flag_value="discover", hidden=True)
@click.option("--info", "site_shortcut", flag_value="about", hidden=True)
@click.pass_context
def main(ctx, catalogue, remote, as_json, site_shortcut):
    """Agent Engineering HQ events, CLI, MCP and A2A.

    Run with no arguments in a terminal to open the interactive menu.
    Human-readable cards are the default on a TTY; agents get Result JSON via
    --json, AGENTENG_OUTPUT=json, or a pipe.
    """
    ctx.ensure_object(dict)
    ctx.obj.update(catalogue=catalogue, remote=remote, as_json=as_json)
    if ctx.invoked_subcommand is None and site_shortcut:
        # Website wording (`agenteng --list-disciplines`) runs the real command.
        ctx.invoke(main.commands[site_shortcut])
        return
    if ctx.invoked_subcommand is None:
        if stdout_is_tty() and stdin_is_tty():
            from .interactive import run_menu

            run_menu(ctx)
        else:
            click.echo(ctx.get_help())


def execute(ctx, request: Request) -> Result:
    """Run one request locally or against --remote; raises transport errors."""
    token = os.getenv("AGENTENG_OPERATOR_TOKEN", "")
    if ctx.obj["remote"]:
        headers = {"Authorization": "Bearer " + token} if token else {}
        response = httpx.post(
            validate_origin(ctx.obj["remote"]) + "/v1/query",
            json=request.model_dump(mode="json", exclude_defaults=True),
            headers=headers,
            timeout=50,
        )
        response.raise_for_status()
        return Result.model_validate(response.json())
    settings = Settings.from_env()
    if ctx.obj["catalogue"]:
        from dataclasses import replace

        settings = replace(settings, catalogue_path=ctx.obj["catalogue"])
    return asyncio.run(Service(settings).execute(request, token=token))


def dispatch(ctx, payload, output=None, *, quiet=False):
    try:
        request = Request.model_validate(payload)
        result = execute(ctx, request)
    except (ValidationError, ValueError, OSError, httpx.HTTPError) as exc:
        raise click.ClickException(str(exc)) from exc
    empty_ok = empty_but_valid(result, request.operation)
    if quiet and (result.status == "ok" or empty_ok):
        return result
    if output and result.artifact:
        try:
            Path(output).write_bytes(result.artifact.encode())
        except OSError as exc:
            raise click.ClickException("Cannot create output; choose a new writable file.") from exc
    forced_json = bool(ctx.obj["as_json"]) or (
        os.environ.get("AGENTENG_OUTPUT", "").strip().lower() == "json"
    )
    if forced_json:
        click.echo(result.model_dump_json(indent=2))
    elif result.artifact and not output:
        click.echo(result.artifact, nl=False)
    elif not stdout_is_tty():
        click.echo(result.model_dump_json(indent=2))
    else:
        from .render import render_result

        render_result(result, request.operation)
    if result.status != "ok" and not empty_ok:
        ctx.exit(1)
    return result


@main.command()
@click.pass_context
def disciplines(ctx):
    """List the twelve disciplines, tool counts and available filters."""
    dispatch(ctx, dict(operation="disciplines"))


@main.command()
@click.option(
    "--discipline", type=click.Choice(list(DISCIPLINES)), help="Only tools in this discipline."
)
@click.option(
    "--kind", type=click.Choice(list(get_args(ToolKind))), help="Only tools of this kind."
)
@click.option(
    "--category", help="Exact source category; use agenteng --json disciplines to find categories."
)
@click.option("--search", "query", default="", help="Match names, aliases, IDs and category tags.")
@click.option(
    "--limit",
    type=click.IntRange(1, 100),
    default=20,
    show_default=True,
    help="Tools per page.",
)
@click.option(
    "--offset", type=click.IntRange(0, 10000), default=0, help="Skip this many tools (next page)."
)
@click.option(
    "--status",
    "tool_status",
    type=click.Choice(["listed", "hold", "deprecated", "all"]),
    default="listed",
    show_default=True,
    help="Listing status to show; all shows every status.",
)
@click.pass_context
def tools(ctx, discipline, kind, category, query, limit, offset, tool_status):
    """Browse the full tool directory offline; alphabetical, paginated and model-free."""
    dispatch(
        ctx,
        dict(
            operation="tools",
            discipline=discipline,
            kind=kind,
            category=category,
            query=query,
            limit=limit,
            offset=offset,
            tool_status=tool_status,
        ),
    )


@main.command()
@click.argument("tool_id")
@click.pass_context
def tool(ctx, tool_id):
    """Read a tool's links, tags, aliases and source provenance.

    TOOL_ID is a tool ID from agenteng tools, for example langgraph.
    """
    dispatch(ctx, dict(operation="tool", tool_id=tool_id))


def local_service(ctx):
    """Build a local Service for ID resolution helpers."""
    from dataclasses import replace

    settings = Settings.from_env()
    if ctx.obj.get("catalogue"):
        settings = replace(settings, catalogue_path=ctx.obj["catalogue"])
    return Service(settings)


def resolve_talk(ctx, identifier: str, event_id: str | None = None):
    """Resolve a session or speaker identifier to a talk session row.

    Exact session or speaker IDs win over text search: IDs such as
    ``agenteng-london-2026-14`` share most tokens with other talks.
    """

    def talk_rows(query: str) -> list[dict]:
        payload = dict(operation="talks", event_id=event_id, query=query, limit=100)
        if ctx.obj.get("remote"):
            result = dispatch(ctx, payload, quiet=True)
        else:
            result = local_service(ctx).lookup(Request(**payload))
        return result.data if isinstance(result.data, list) else []

    exact = [
        row
        for row in talk_rows("")
        if row.get("id") == identifier or row.get("speaker_id") == identifier
    ]
    if exact:
        return exact[0]
    rows = talk_rows(identifier)
    if len(rows) == 1:
        return rows[0]
    return None


def city_shortcuts(command):
    """Hidden ``--london`` and ``--sf`` flags, as written on the website, for ``--city``."""
    command = click.option("--london", "city", flag_value="London", hidden=True)(command)
    return click.option("--sf", "--san-francisco", "city", flag_value="San Francisco", hidden=True)(
        command
    )


def city_event_id(ctx, city: str) -> str:
    """Pick a city's event: the next upcoming one, else the most recent."""
    result = dispatch(ctx, dict(operation="events", city=city), quiet=True)
    rows = result.data if result.status == "ok" and isinstance(result.data, list) else []
    if not rows:
        raise click.ClickException(f"No published events in {city}.")
    ahead = sorted(
        (e for e in rows if e.get("state") in {"ongoing", "upcoming"}),
        key=lambda e: (e.get("state") != "ongoing", e.get("date") or ""),
    )
    if ahead:
        return ahead[0]["id"]
    return max(rows, key=lambda e: e.get("date") or "")["id"]


def event_or_city(ctx, event_id: str | None, city: str | None = None) -> str | None:
    """An EVENT_ID argument may also be a city (``london``, ``san-francisco``)."""
    if event_id:
        named = canonical_city(event_id)
        if named in {"London", "San Francisco"}:
            return city_event_id(ctx, named)
        return event_id
    if city:
        return city_event_id(ctx, canonical_city(city))
    return None


@main.command()
@click.argument("where", metavar="[CITY]", required=False)
@click.option("--city", help="London or San Francisco (slugs such as san-francisco work).")
@city_shortcuts
@click.option("--upcoming", "--next", is_flag=True, help="Only upcoming events.")
@click.option("--past", "--history", "--previous", is_flag=True, help="Only past events.")
@click.pass_context
def events(ctx, where, city, upcoming, past):
    """List events with published date precision and current state.

    CITY is optional: London or San Francisco (slugs such as san-francisco work).
    """
    dispatch(ctx, dict(operation="events", city=city or where, upcoming=upcoming, past=past))


@main.command()
@click.argument("event_id", required=False)
@city_shortcuts
@click.pass_context
def event(ctx, event_id, city=None):
    """Read one event by its published ID (or a city: london, san-francisco).

    EVENT_ID is an event ID from agenteng events, or a city. Omit it in a terminal to pick one.
    """
    from .interactive import require_event_id

    event_id = event_or_city(ctx, event_id, city)
    dispatch(ctx, dict(operation="event", event_id=require_event_id(ctx, event_id)))


@main.command()
@click.argument("event_id", required=False)
@click.option("--topic", help="Only sessions matching this text, for example memory.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "ics"]),
    default="json",
    show_default=True,
    help="json for Result JSON, ics for a calendar file.",
)
@click.option(
    "--output", type=click.Path(dir_okay=False), help="Write an .ics calendar when --format ics."
)
@city_shortcuts
@click.pass_context
def agenda(ctx, event_id, topic, output_format, output, city=None):
    """Read an event's public agenda; optionally export .ics.

    EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.
    """
    from .interactive import require_event_id

    event_id = event_or_city(ctx, event_id, city)
    dispatch(
        ctx,
        dict(
            operation="agenda",
            event_id=require_event_id(ctx, event_id),
            topic=topic,
            format=output_format,
        ),
        output,
    )


@main.command()
@click.option("--event", "event_id", help="Only speakers at this event ID.")
@click.option("--city", help="Only speakers in London or San Francisco.")
@city_shortcuts
@click.option("--search", "query", default="", help="Match name, company, talk title or abstract.")
@click.pass_context
def speakers(ctx, event_id, city, query):
    """List published speakers with roles, companies, talks and abstracts."""
    dispatch(ctx, dict(operation="speakers", event_id=event_id, city=city, query=query))


@main.command("speaker")
@click.argument("speaker_id")
@click.option("--event", "event_id", help="Event ID, when the speaker appears at more than one.")
@click.pass_context
def speaker_detail(ctx, speaker_id, event_id):
    """Read one speaker: bio fields, links, projects, disciplines and full abstract.

    SPEAKER_ID is a speaker ID from agenteng speakers, for example samuel-colvin.
    """
    dispatch(ctx, dict(operation="speaker", speaker_id=speaker_id, event_id=event_id))


@main.command("inspect", hidden=True)
@click.option("--speaker", "speaker_id", required=True, help="Speaker ID, as on the website.")
@click.option("--event", "event_id")
@click.pass_context
def inspect_speaker(ctx, speaker_id, event_id):
    """Website wording for `agenteng speaker SPEAKER_ID`."""
    ctx.invoke(speaker_detail, speaker_id=speaker_id, event_id=event_id)


@main.command()
@click.option("--event", "event_id", help="Only talks at this event ID.")
@click.option("--search", "query", default="", help="Match talk title, abstract or speaker.")
@click.option("--speaker", "speaker_id", help="Only talks by this speaker ID.")
@click.pass_context
def talks(ctx, event_id, query, speaker_id):
    """List published talks with full abstracts."""
    dispatch(
        ctx,
        dict(operation="talks", event_id=event_id, query=query, speaker_id=speaker_id),
    )


@main.command("talk")
@click.argument("identifier", required=False)
@click.option("--event", "event_id", help="Only look in this event ID.")
@click.option("--search", "query", default="", help="Find the talk by title or abstract text.")
@click.pass_context
def talk_detail(ctx, identifier, event_id, query):
    """Read one talk by session ID, speaker ID, or --search text.

    IDENTIFIER is a session ID or speaker ID from agenteng talks.
    """
    payload = dict(operation="talk", event_id=event_id, query=query)
    if identifier:
        row = resolve_talk(ctx, identifier, event_id)
        if row:
            payload["session_id"] = row["id"]
            payload["query"] = ""
        elif not query:
            payload["query"] = identifier
    dispatch(ctx, payload)


@main.command()
@click.option("--event", "event_id", help="Only FAQ entries for this event ID.")
@click.option("--search", "query", default="", help="Match FAQ question or answer text.")
@click.pass_context
def faq(ctx, event_id, query):
    """Read published FAQ answers from the conference website."""
    dispatch(ctx, dict(operation="faq", event_id=event_id, query=query))


@main.command()
@click.argument("event_id", required=False)
@city_shortcuts
@click.pass_context
def venue(ctx, event_id, city=None):
    """Read venue address, tour link, track and accessibility notes.

    EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.
    """
    from .interactive import require_event_id

    event_id = event_or_city(ctx, event_id, city)
    dispatch(ctx, dict(operation="venue", event_id=require_event_id(ctx, event_id)))


@main.command()
@click.option("--city", help="Only sponsors in London or San Francisco.")
@city_shortcuts
@click.pass_context
def sponsors(ctx, city):
    """List published sponsors and London support options."""
    dispatch(ctx, dict(operation="sponsors", city=city))


@main.command()
@click.pass_context
def conduct(ctx):
    """Read the published code of conduct summary and report contact."""
    dispatch(ctx, dict(operation="conduct"))


@main.command()
@click.pass_context
def themes(ctx):
    """List published program themes from the website."""
    dispatch(ctx, dict(operation="themes"))


AT_HELP = "Pretend it is this time: ISO (2026-10-16T10:15) or HH:MM on the event day."


@main.command("now")
@click.argument("event_id", required=False)
@click.option("--at", "at", help=AT_HELP)
@click.option("--screen", is_flag=True, help="Full-screen venue display; same as `agenteng live`.")
@city_shortcuts
@click.pass_context
def now_cmd(ctx, event_id, at, screen, city=None):
    """Show what is on now from the published timed agenda.

    EVENT_ID is an event ID or a city; defaults to the live conference.
    """
    event_id = event_or_city(ctx, event_id, city)
    if screen:
        ctx.invoke(live_cmd, event_id=event_id, at=at)
        return
    dispatch(ctx, dict(operation="now", event_id=event_id, at=resolve_at(ctx, at, event_id)))


@main.command("next")
@click.argument("event_id", required=False)
@click.option("--at", "at", help=AT_HELP)
@city_shortcuts
@click.pass_context
def next_cmd(ctx, event_id, at, city=None):
    """Show the next published session from the timed agenda.

    EVENT_ID is an event ID or a city; defaults to the live conference.
    """
    event_id = event_or_city(ctx, event_id, city)
    dispatch(ctx, dict(operation="next", event_id=event_id, at=resolve_at(ctx, at, event_id)))


def resolve_at(ctx, at: str | None, event_id: str | None):
    """Parse --at. HH:MM uses the event's own date; no offset means event local time."""
    if not at:
        return None
    import re
    from datetime import datetime

    if re.fullmatch(r"\d{1,2}:\d{2}", at.strip()):
        snapshot = dispatch(ctx, dict(operation="live", event_id=event_id), quiet=True)
        day = (
            (snapshot.data.get("event") or {}).get("date")
            if isinstance(snapshot.data, dict)
            else None
        )
        if not day:
            raise click.ClickException("--at HH:MM needs an event with a published date.")
        at = f"{day}T{int(at.split(':')[0]):02d}:{at.split(':')[1]}"
    try:
        return datetime.fromisoformat(at.strip()).isoformat()
    except ValueError as exc:
        raise click.ClickException("--at must be ISO time (2026-10-16T10:15) or HH:MM.") from exc


@main.command("live")
@click.option("--event", "event_id", help="Event ID or city; defaults to the live conference.")
@click.option(
    "--refresh",
    type=click.IntRange(1, 3600),
    default=30,
    show_default=True,
    help="Seconds between screen refreshes.",
)
@click.option("--at", "at", help=AT_HELP + " The clock then runs forward from it.")
@click.option("--once", is_flag=True, help="Draw one frame and exit (no full screen).")
@city_shortcuts
@click.pass_context
def live_cmd(ctx, event_id=None, refresh=30, at=None, once=False, city=None):
    """Full-screen now/next board for venue screens. Ctrl-C exits.

    Piped or with --json it prints one Result JSON snapshot instead.
    """
    from .output import use_json

    event_id = event_or_city(ctx, event_id, city)
    start_at = resolve_at(ctx, at, event_id)
    payload = dict(operation="live", event_id=event_id, at=start_at)
    if use_json(ctx):
        dispatch(ctx, payload)
        return
    from .render import run_live_screen

    try:
        run_live_screen(ctx, payload, refresh=refresh, once=once)
    except (ValidationError, ValueError, OSError, httpx.HTTPError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.command()
@click.argument("event_id", required=False)
@city_shortcuts
@click.pass_context
def tickets(ctx, event_id, city=None):
    """Read published prices and the official registration link.

    EVENT_ID is an event ID or a city (london, san-francisco). Omit it in a terminal to pick one.
    """
    from .interactive import require_event_id

    event_id = event_or_city(ctx, event_id, city)
    dispatch(ctx, dict(operation="tickets", event_id=require_event_id(ctx, event_id)))


@main.command()
@click.option("--event", "event_id", help="Only recordings from this event ID.")
@click.option("--city", help="Only recordings from London or San Francisco.")
@city_shortcuts
@click.pass_context
def recordings(ctx, event_id, city):
    """Find published recordings."""
    dispatch(ctx, dict(operation="recordings", event_id=event_id, city=city))


@main.command()
@click.argument("query")
@click.option("--event", "event_id", help="Only search this event ID.")
@click.option("--city", help="Only search London or San Francisco.")
@click.pass_context
def search(ctx, query, event_id, city):
    """Search public sources without model calls.

    QUERY is the text to find in published talks, speakers, FAQ, themes and site pages.
    """
    dispatch(ctx, dict(operation="search", query=query, event_id=event_id, city=city))


@main.command()
@click.argument("query")
@click.option("--event", "event_id", help="Only answer from this event ID.")
@click.option(
    "--engine",
    type=click.Choice(["lookup", "auto", "standard", "rlm"]),
    default="lookup",
    show_default=True,
    help="lookup needs no model; standard and rlm need a server-side enabled model.",
)
@click.pass_context
def ask(ctx, query, event_id, engine):
    """Find attributed excerpts, or explicitly request an enabled model engine.

    QUERY is a plain question, for example "When is the next London conference?".
    """
    dispatch(ctx, dict(operation="ask", query=query, event_id=event_id, engine=engine))


@main.command()
@click.pass_context
def participate(ctx):
    """Find organizer contact and guidance for talk/event ideas."""
    dispatch(ctx, dict(operation="participate"))


def city_choice(ctx, param, value):
    if value is None:
        return None
    named = canonical_city(value)
    if named not in {"London", "San Francisco"}:
        raise click.BadParameter("choose London or San Francisco (or london, san-francisco, sf)")
    return named


@main.command()
@click.option("--city", callback=city_choice, help="London or San Francisco.")
@city_shortcuts
@click.pass_context
def discover(ctx, city):
    """Find AgentEng London/San Francisco events and agent connection details."""
    dispatch(ctx, dict(operation="discover", city=city))


@main.command()
@click.option("--chair", "section", flag_value="chair", help="Only the conference chair.")
@click.option(
    "--organiser", "--organizer", "section", flag_value="organiser", help="Only the organiser."
)
@click.option("--connect", "section", flag_value="connect", help="Only how to connect agents.")
@click.pass_context
def about(ctx, section):
    """What Agent Engineering is, who runs it, and how to connect your agent."""
    dispatch(ctx, dict(operation="about", section=section))


@main.command("whoami", hidden=True)
@click.option("--chair", is_flag=True, help="Show the conference chair (website wording).")
@click.pass_context
def whoami(ctx, chair):
    """Website wording for `agenteng about --chair`."""
    ctx.invoke(about, section="chair")


@main.command()
@click.argument("section", required=False, type=click.Choice(["manifesto", "mindset", "reading"]))
@click.pass_context
def hq(ctx, section):
    """Agent Engineering HQ: the manifesto, the mindset and further reading.

    SECTION is optional: manifesto, mindset or reading. Omit it for all three.
    """
    dispatch(ctx, dict(operation="hq", section=section))


@main.command()
@click.option("--event", "event_id", help="Event ID or city; defaults to the London conference.")
@click.option(
    "--size",
    type=click.Choice(["4", "5"]),
    default="5",
    show_default=True,
    help="Grid size: 5x5 with a free centre, or 4x4.",
)
@click.option(
    "--seed", type=click.IntRange(0, 2**53), help="Same seed, same card. Printed on every card."
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "svg", "html", "json"]),
    help="Printable text, SVG or HTML. Default: a card in the terminal, JSON when piped.",
)
@click.option("--output", type=click.Path(dir_okay=False), help="Write the card to a file.")
@click.option("--play", is_flag=True, help="Mark squares as you hear them (terminal only).")
@city_shortcuts
@click.pass_context
def bingo(ctx, event_id, size, seed, output_format, output, play, city=None):
    """Talk bingo from published talk terms. Local only; nothing is sent."""
    event_id = event_or_city(ctx, event_id, city)
    if output and not output_format:
        suffix = Path(output).suffix.lower()
        output_format = {".svg": "svg", ".html": "html", ".htm": "html"}.get(suffix, "text")
    payload = dict(
        operation="bingo",
        event_id=event_id,
        size=int(size),
        seed=seed,
        format=output_format or "json",
    )
    if play:
        if not (stdout_is_tty() and stdin_is_tty()):
            raise click.ClickException(
                "--play needs a terminal; use --format text to print a card."
            )
        result = dispatch(ctx, {**payload, "format": "json"}, quiet=True)
        if result.status != "ok":
            dispatch(ctx, payload)
            return
        from .render import play_bingo

        play_bingo(result)
        return
    result = dispatch(ctx, payload, output)
    if output and result.artifact:
        click.echo(f"Wrote {output}", err=True)


@main.command()
@click.argument(
    "client", type=click.Choice(["a2a", "mcp", "acp", "codex", "claude-code", "cursor", "generic"])
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"]),
    default="stdio",
    show_default=True,
    help="stdio runs agenteng mcp locally; http uses the hosted MCP server.",
)
@click.option(
    "--url",
    default=Settings.public_url,
    show_default=True,
    help="Hosted server base URL for A2A or HTTP MCP.",
)
def connect(client, transport, url):
    """Print A2A, MCP or ACP setup instructions without changing client configuration.

    CLIENT is a2a, mcp, acp, codex, claude-code, cursor or generic. Output is plain text.
    """
    try:
        click.echo(connection(client, transport, url))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@main.command("code")
@click.argument("prompt", nargs=-1)
@click.option(
    "--agent", "agent_name", help="Agent to launch (see --list). Default: first installed."
)
@click.option(
    "--agent-command", help="Custom ACP agent command line, for example 'my-agent --acp'."
)
@click.option(
    "--list", "list_agents", is_flag=True, help="Show known ACP agents and which are on PATH."
)
@click.option(
    "--cwd",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Working directory for the agent session (default: current directory).",
)
@click.option(
    "--context",
    "context_ids",
    multiple=True,
    help="Attach a talk, event, speaker or tool:ID record to the prompt. Repeatable.",
)
@click.option("--no-mcp", is_flag=True, help="Do not attach the AgentEng MCP server.")
@click.option("--npx", is_flag=True, help="Launch a missing npm-distributed agent through npx.")
@click.option("--show-thoughts", is_flag=True, help="Show the agent's thought chunks.")
@click.option(
    "--allow-always-option",
    is_flag=True,
    help="Also offer the agent's 'allow always' choice in permission prompts (hidden by default).",
)
@click.option(
    "--chat",
    "chat_flag",
    is_flag=True,
    help="Keep one session open for several turns (default with no PROMPT in a terminal).",
)
@click.option("--json", "json_events", is_flag=True, help="Stream newline-delimited JSON events.")
@click.pass_context
def code(
    ctx,
    prompt,
    agent_name,
    agent_command,
    list_agents,
    cwd,
    context_ids,
    no_mcp,
    npx,
    show_thoughts,
    allow_always_option,
    chat_flag,
    json_events,
):
    """Experimental: drive an ACP coding agent with AgentEng context (install [acp]).

    Spawns the agent over the Agent Client Protocol, attaches the AgentEng MCP
    server and streams its reply. Every permission request is asked in the
    terminal; without a terminal it is rejected. Nothing is auto-approved.

    With no PROMPT in a terminal (or with --chat) it opens a chat on one session:
    /help, /context ID, /agent, /exit or Ctrl-D. Ctrl-C cancels the current turn.
    With --chat and piped stdin, each line is one turn.

    PROMPT is optional free text for one turn.

    Example: agenteng code --agent claude "scaffold a demo of talk agenteng-london-2026-14"
    """
    from .acp_agents import AGENTS, REGISTRY_URL
    from .output import use_json

    as_json = json_events or use_json(ctx)
    if list_agents:
        rows = [spec.as_dict() for spec in AGENTS]
        if as_json:
            click.echo(json.dumps({"registry": REGISTRY_URL, "agents": rows}, indent=2))
        else:
            from .render import render_acp_agents

            render_acp_agents(rows, REGISTRY_URL)
        return
    text = " ".join(prompt).strip()
    interactive = stdin_is_tty()
    # Chat: --chat, or no prompt in a terminal. Piped stdin with --chat means one turn per line.
    chat = chat_flag or (not text and interactive and not as_json)
    if not chat and not text and not interactive:
        text = click.get_text_stream("stdin").read().strip()
    if not chat and not text:
        raise click.UsageError(
            'Give a prompt, for example: agenteng code "explain talk agenteng-london-2026-2", '
            "or run agenteng code in a terminal (or with --chat) to chat."
        )
    argv = resolve_agent_argv(agent_name, agent_command, npx)
    run_code(
        ctx,
        argv,
        text,
        chat=chat,
        cwd=cwd,
        context_ids=list(context_ids),
        no_mcp=no_mcp,
        show_thoughts=show_thoughts,
        allow_always=allow_always_option,
        as_json=as_json,
    )


def resolve_agent_argv(agent_name=None, agent_command=None, npx=False) -> list[str]:
    """Command line for --agent / --agent-command / the first installed agent."""
    import shlex
    import shutil

    from .acp_agents import default_agent, find_agent

    try:
        if agent_command:
            argv = shlex.split(agent_command)
            if not argv:
                raise LookupError("--agent-command is empty.")
            argv[0] = shutil.which(argv[0]) or argv[0]
            return argv
        spec = find_agent(agent_name) if agent_name else default_agent()
        return spec.argv(npx=npx)
    except LookupError as exc:
        raise click.ClickException(str(exc)) from exc


def run_code(
    ctx,
    argv: list[str],
    text: str,
    *,
    chat: bool,
    cwd: str | None = None,
    context_ids: list[str] | None = None,
    no_mcp: bool = False,
    show_thoughts: bool = False,
    allow_always: bool = False,
    as_json: bool = False,
) -> None:
    """Single-shot turn or chat loop on one ACP session (shared by agenteng code and the menu)."""
    try:
        from . import acp_client
    except ImportError as exc:
        raise click.ClickException("Install agenteng[acp] for agenteng code.") from exc

    global_args = []
    if ctx.obj.get("remote"):
        global_args += ["--remote", ctx.obj["remote"]]
    if ctx.obj.get("catalogue"):
        global_args += ["--catalogue", str(Path(ctx.obj["catalogue"]).resolve())]

    sink = acp_client.JsonSink() if as_json else acp_client.RichSink(show_thoughts=show_thoughts)
    mcp_servers = []
    if not no_mcp:
        if acp_client.mcp_available():
            mcp_servers.append(acp_client.mcp_server_config(global_args))
        else:
            sink.emit(
                "warning",
                message="The mcp package is missing, so AgentEng tools are not attached. "
                "Install agenteng[acp] (includes mcp) to attach them.",
            )
    service = None if ctx.obj.get("remote") else local_service(ctx)
    records = []
    if service is not None:
        records = acp_client.context_records(service, text, list(context_ids or []))
    interactive = stdin_is_tty()
    if not interactive:
        prompter = None
    elif as_json:
        prompter = acp_client.terminal_prompter(err=True, async_input=True)
    else:
        prompter = acp_client.terminal_prompter(sink.console, sink=sink, async_input=True)
    session = acp_client.AgentSession(
        argv,
        cwd=cwd or os.getcwd(),
        sink=sink,
        prompter=prompter,
        mcp_servers=mcp_servers,
        context_ids=[f"{r['kind']}:{r['id']}" for r in records],
        allow_always=allow_always,
    )

    async def go() -> str:
        async with session:
            if not chat:
                blocks = acp_client.build_prompt(text, records, mcp_attached=bool(mcp_servers))
                return await session.turn(blocks, handle_sigint=True)
            if interactive and not as_json:
                info = session.agent_info.get("agent_info") or {}
                label = info.get("title") or info.get("name") or Path(argv[0]).name
                sink.emit(
                    "info", message="Chat started. /help for commands, /exit or Ctrl-D to end."
                )
                reader = acp_client.tty_reader(label)
            else:
                reader = acp_client.line_reader()
            return await acp_client.run_chat(
                session,
                reader,
                service=service,
                mcp_attached=bool(mcp_servers),
                first_prompt=text,
                records=records,
            )

    try:
        stop_reason = asyncio.run(go())
    except acp_client.AgentError as exc:
        if as_json:
            sink.emit("error", message=str(exc))
            ctx.exit(1)
        raise click.ClickException(str(exc)) from exc
    except KeyboardInterrupt:
        ctx.exit(130)
    if chat:
        if not as_json:
            sink.emit("info", message=f"Chat ended after {session.turns} turn(s).")
        return
    if stop_reason == "cancelled":
        ctx.exit(130)
    if stop_reason not in ("end_turn", "max_tokens", "max_turn_requests"):
        ctx.exit(1)


@main.command("query")
@click.argument("payload")
@click.pass_context
def raw_query(ctx, payload):
    """Execute the same JSON request accepted by MCP and A2A.

    PAYLOAD is one Request JSON object, for example '{"operation":"events"}'.
    """
    try:
        parsed = json.loads(payload)
    except ValueError as exc:
        raise click.ClickException("Payload must be JSON.") from exc
    dispatch(ctx, parsed)


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Address to listen on.")
@click.option(
    "--port",
    default=8000,
    type=click.IntRange(1, 65535),
    show_default=True,
    help="Port to listen on.",
)
@click.option(
    "--access-log/--no-access-log",
    default=False,
    show_default=True,
    help="Per-request access lines (client address, path, status). Off: the host's own "
    "request log is enough, and AgentEng adds none.",
)
def serve(host, port, access_log):
    """Run the combined HTTP, MCP and A2A server (install [server])."""
    try:
        import uvicorn

        from .server import create_app
    except ImportError as exc:
        raise click.ClickException("Install agenteng[server] for hosted transports.") from exc
    uvicorn.run(create_app(), host=host, port=port, access_log=access_log)


@main.command("mcp")
@click.pass_context
def mcp_stdio(ctx):
    """Run one-tool MCP over stdio (install [mcp])."""
    try:
        from .mcp import create_mcp
    except ImportError as exc:
        raise click.ClickException("Install agenteng[mcp] for MCP.") from exc
    if ctx.obj["remote"]:
        from .remote import RemoteService

        service = RemoteService(ctx.obj["remote"])
    else:
        from dataclasses import replace

        settings = Settings.from_env()
        if ctx.obj["catalogue"]:
            settings = replace(settings, catalogue_path=ctx.obj["catalogue"])
        service = Service(settings)
    create_mcp(service, stdio=True).run(transport="stdio")


if __name__ == "__main__":
    main()
