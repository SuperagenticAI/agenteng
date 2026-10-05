"""Public event CLI. Optional protocol and model dependencies load on demand."""

import asyncio
import json
import os
from pathlib import Path

import click
import httpx
from pydantic import ValidationError

from . import __version__
from .config import Settings
from .models import Request, Result
from .service import Service
from .discovery import connection, validate_origin
from .participation import Draft, Inbox, PRIVATE_OPERATIONS
from .tool_directory import DISCIPLINES, ToolKind
from .output import stdout_is_tty, stdin_is_tty
from typing import get_args


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
@click.pass_context
def main(ctx, catalogue, remote, as_json):
    """Agent Engineering HQ events, CLI, MCP and A2A.

    Run with no arguments in a terminal to open the interactive menu.
    Human-readable cards are the default on a TTY; agents get Result JSON via
    --json, AGENTENG_OUTPUT=json, or a pipe.
    """
    ctx.ensure_object(dict)
    ctx.obj.update(catalogue=catalogue, remote=remote, as_json=as_json)
    if ctx.invoked_subcommand is None:
        if stdout_is_tty() and stdin_is_tty():
            from .interactive import run_menu

            run_menu(ctx)
        else:
            click.echo(ctx.get_help())


def dispatch(ctx, payload, output=None, *, quiet=False):
    try:
        request = Request.model_validate(payload)
        token = os.getenv(
            "AGENTENG_PARTICIPANT_TOKEN"
            if request.operation in PRIVATE_OPERATIONS
            else "AGENTENG_OPERATOR_TOKEN",
            "",
        )
        if ctx.obj["remote"]:
            headers = {"Authorization": "Bearer " + token} if token else {}
            response = httpx.post(
                validate_origin(ctx.obj["remote"]) + "/v1/query",
                json=request.model_dump(mode="json"),
                headers=headers,
                timeout=50,
            )
            response.raise_for_status()
            result = Result.model_validate(response.json())
        else:
            settings = Settings.from_env()
            if ctx.obj["catalogue"]:
                from dataclasses import replace

                settings = replace(settings, catalogue_path=ctx.obj["catalogue"])
            result = asyncio.run(Service(settings).execute(request, token=token))
    except (ValidationError, ValueError, OSError, httpx.HTTPError) as exc:
        raise click.ClickException(str(exc)) from exc
    if quiet and result.status == "ok":
        return result
    if output and result.artifact:
        try:
            if request.operation.startswith("proposal_"):
                write_private(output, result.artifact)
            else:
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
    if result.status != "ok":
        ctx.exit(1)
    return result


@main.command()
@click.pass_context
def disciplines(ctx):
    """List the twelve disciplines, tool counts and available filters."""
    dispatch(ctx, dict(operation="disciplines"))


@main.command()
@click.option("--discipline", type=click.Choice(list(DISCIPLINES)))
@click.option("--kind", type=click.Choice(list(get_args(ToolKind))))
@click.option(
    "--category", help="Exact source category; use agenteng --json disciplines to find categories."
)
@click.option("--search", "query", default="", help="Match names, aliases, IDs and category tags.")
@click.option("--limit", type=click.IntRange(1, 100), default=20, show_default=True)
@click.option("--offset", type=click.IntRange(0, 10000), default=0)
@click.option(
    "--status",
    "tool_status",
    type=click.Choice(["listed", "hold", "deprecated", "all"]),
    default="listed",
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
    """Read a tool's links, tags, aliases and source provenance."""
    dispatch(ctx, dict(operation="tool", tool_id=tool_id))


def write_private(path, text):
    """Never replace an existing file or follow a destination symlink."""
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(text)


@main.command()
@click.option("--city")
@click.option("--upcoming", is_flag=True)
@click.option("--past", is_flag=True)
@click.pass_context
def events(ctx, city, upcoming, past):
    """List events with published date precision and current state."""
    dispatch(ctx, dict(operation="events", city=city, upcoming=upcoming, past=past))


@main.command()
@click.argument("event_id", required=False)
@click.pass_context
def event(ctx, event_id):
    """Read one event by its published ID."""
    from .interactive import require_event_id

    dispatch(ctx, dict(operation="event", event_id=require_event_id(ctx, event_id)))


@main.command()
@click.argument("event_id", required=False)
@click.option("--topic")
@click.pass_context
def agenda(ctx, event_id, topic):
    """Read an event's public agenda."""
    from .interactive import require_event_id

    dispatch(
        ctx,
        dict(operation="agenda", event_id=require_event_id(ctx, event_id), topic=topic),
    )


@main.command()
@click.option("--event", "event_id")
@click.option("--city")
@click.pass_context
def speakers(ctx, event_id, city):
    """List published speakers."""
    dispatch(ctx, dict(operation="speakers", event_id=event_id, city=city))


@main.command()
@click.argument("event_id", required=False)
@click.pass_context
def tickets(ctx, event_id):
    """Read published prices and the official registration link."""
    from .interactive import require_event_id

    dispatch(ctx, dict(operation="tickets", event_id=require_event_id(ctx, event_id)))


@main.command()
@click.option("--event", "event_id")
@click.option("--city")
@click.pass_context
def recordings(ctx, event_id, city):
    """Find published recordings."""
    dispatch(ctx, dict(operation="recordings", event_id=event_id, city=city))


@main.command()
@click.argument("query")
@click.option("--event", "event_id")
@click.option("--city")
@click.pass_context
def search(ctx, query, event_id, city):
    """Search public sources without model calls."""
    dispatch(ctx, dict(operation="search", query=query, event_id=event_id, city=city))


@main.command()
@click.argument("query")
@click.option("--event", "event_id")
@click.option(
    "--engine", type=click.Choice(["lookup", "auto", "standard", "rlm"]), default="lookup"
)
@click.pass_context
def ask(ctx, query, event_id, engine):
    """Find attributed excerpts, or explicitly request an enabled model engine."""
    dispatch(ctx, dict(operation="ask", query=query, event_id=event_id, engine=engine))


@main.command()
@click.argument("event_id", required=False)
@click.option("--interest", "interests", multiple=True)
@click.option("--format", "output_format", type=click.Choice(["json", "ics"]), default="json")
@click.option("--output", type=click.Path(dir_okay=False))
@click.pass_context
def plan(ctx, event_id, interests, output_format, output):
    """Select sessions by published text and optionally export a calendar."""
    from .interactive import require_event_id

    dispatch(
        ctx,
        dict(
            operation="plan",
            event_id=require_event_id(ctx, event_id),
            interests=list(interests),
            format=output_format,
        ),
        output,
    )


@main.command()
@click.pass_context
def participate(ctx):
    """Find organizer contact and guidance for talk/event ideas."""
    dispatch(ctx, dict(operation="participate"))


@main.command()
@click.option("--city", type=click.Choice(["London", "San Francisco"]))
@click.pass_context
def discover(ctx, city):
    """Find AgentEng London/San Francisco events and agent connection details."""
    dispatch(ctx, dict(operation="discover", city=city))


@main.command()
@click.argument("client", type=click.Choice(["codex", "claude-code", "cursor", "generic"]))
@click.option("--transport", type=click.Choice(["stdio", "http"]), default="stdio")
@click.option("--url", default=Settings.public_url)
def connect(client, transport, url):
    """Print MCP setup instructions; never modify a client's configuration."""
    try:
        click.echo(connection(client, transport, url))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


@main.group()
def proposal():
    """Draft ideas for London/San Francisco; private intake requires organizer access."""


@proposal.command("draft")
@click.option("--city", required=True, type=click.Choice(["London", "San Francisco"]))
@click.option(
    "--kind", type=click.Choice(["talk", "workshop", "event_idea", "feedback"]), default="talk"
)
@click.option("--title", default="")
@click.option("--abstract", default="")
@click.option("--audience", default="")
@click.option("--outcome", "outcomes", multiple=True)
@click.option("--speaker-name", default="")
@click.option("--contact-email", default="")
@click.option("--event", "event_id")
@click.option("--interactive", is_flag=True)
@click.option("--output", type=click.Path(dir_okay=False))
@click.pass_context
def proposal_draft(
    ctx,
    city,
    kind,
    title,
    abstract,
    audience,
    outcomes,
    speaker_name,
    contact_email,
    event_id,
    interactive,
    output,
):
    """Create a local draft; default target is a possible future event."""
    if interactive:
        title = title or click.prompt("Working title")
        abstract = abstract or click.prompt("Short abstract or idea")
        audience = audience or click.prompt("Intended audience")
        if kind in {"talk", "workshop"}:
            speaker_name = speaker_name or click.prompt("Speaker name")
            outcomes = outcomes or (click.prompt("One practical learning outcome"),)
    dispatch(
        ctx,
        {
            "operation": "proposal_draft",
            "draft": {
                "kind": kind,
                "city": city,
                "title": title,
                "abstract": abstract,
                "audience": audience,
                "outcomes": list(outcomes),
                "speaker_name": speaker_name,
                "contact_email": contact_email,
                "event_id": event_id,
                "future_event": not bool(event_id),
            },
        },
        output,
    )


@main.command()
@click.option("--city", type=click.Choice(["London", "San Francisco"]))
@click.option(
    "--kind",
    type=click.Choice(["talk", "workshop", "event_idea", "feedback"]),
    default="event_idea",
)
@click.option("--output", type=click.Path(dir_okay=False))
@click.pass_context
def engage(ctx, city, kind, output):
    """Build a future-event idea through a short guided conversation."""
    city = city or click.prompt("City", type=click.Choice(["London", "San Francisco"]))
    ctx.invoke(proposal_draft, city=city, kind=kind, interactive=True, output=output)


def read_draft(path):
    try:
        if Path(path).stat().st_size > 65536:
            raise ValueError("Draft is too large")
        return Draft.model_validate_json(Path(path).read_bytes()).model_dump(mode="json")
    except (OSError, ValueError) as exc:
        raise click.ClickException("Use a valid draft JSON file of at most 64 KiB.") from exc


@proposal.command("preview")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def proposal_preview(ctx, file):
    """Check a draft locally; no external submission or stored receipt."""
    dispatch(ctx, {"operation": "proposal_preview", "draft": read_draft(file)})


@proposal.command("export")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format", "draft_format", type=click.Choice(["json", "markdown"]), default="markdown"
)
@click.option("--output", type=click.Path(dir_okay=False))
@click.pass_context
def proposal_export(ctx, file, draft_format, output):
    """Export your draft for editing or sending yourself."""
    dispatch(
        ctx,
        {"operation": "proposal_export", "draft": read_draft(file), "draft_format": draft_format},
        output,
    )


@proposal.command("submit")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def proposal_submit(ctx, file):
    """Prepare an exact private preview, then ask for explicit confirmation."""
    draft = read_draft(file)
    preview = dispatch(ctx, {"operation": "proposal_prepare", "draft": draft}, quiet=True)
    click.echo(json.dumps(preview.data, default=str, indent=2), err=True)
    click.confirm(
        "Send this exact draft to the private Agent Engineering HQ inbox?", abort=True, err=True
    )
    dispatch(
        ctx,
        {
            "operation": "proposal_submit",
            "draft": draft,
            "preview_reference": preview.data["preview_reference"],
            "confirmed": True,
        },
    )


@proposal.command("status")
@click.argument("receipt")
@click.pass_context
def proposal_status(ctx, receipt):
    """Read your own submission using the participant credential."""
    dispatch(ctx, {"operation": "proposal_status", "receipt": receipt})


@proposal.command("withdraw")
@click.argument("receipt")
@click.pass_context
def proposal_withdraw(ctx, receipt):
    """Confirm withdrawal and erase active proposal content."""
    click.confirm(
        "Withdraw this submission and erase its active proposal content?", abort=True, err=True
    )
    dispatch(ctx, {"operation": "proposal_withdraw", "receipt": receipt, "confirmed": True})


@main.group()
@click.pass_context
def inbox(ctx):
    """Organizer-only local inbox administration; requires private filesystem access."""
    if ctx.obj["remote"]:
        raise click.ClickException("Inbox administration runs only on the private store host.")
    settings = Settings.from_env()
    if not settings.inbox_path:
        raise click.ClickException("Configure AGENTENG_INBOX on the private store host.")
    ctx.obj["inbox"] = Inbox(
        settings.inbox_path,
        retention_days=settings.intake_retention_days,
        capacity=settings.intake_capacity,
    )


@inbox.command("issue-access")
@click.option("--days", type=click.IntRange(1, 365), default=30)
@click.option("--output", required=True, type=click.Path(dir_okay=False))
@click.pass_context
def issue_access(ctx, days, output):
    """Write a new per-participant credential to a new private file."""
    try:
        # Check the destination before issuing an otherwise unusable credential.
        if Path(output).exists() or Path(output).is_symlink():
            raise OSError("Destination exists")
        token = ctx.obj["inbox"].issue_caller(days)
        write_private(output, token + "\n")
    except (OSError, ValueError) as exc:
        raise click.ClickException(
            "Could not issue access; choose a new writable private file."
        ) from exc
    click.echo("Participant credential written. Share it privately with that participant only.")


@inbox.command("list")
@click.pass_context
def inbox_list(ctx):
    """Show the latest 100 private submissions to the local organizer."""
    click.echo(json.dumps(ctx.obj["inbox"].listing(), default=str, indent=2))


@inbox.command("review")
@click.argument("receipt")
@click.option(
    "--status",
    required=True,
    type=click.Choice(["under_review", "needs_information", "accepted", "declined"]),
)
@click.pass_context
def inbox_review(ctx, receipt, status):
    """Record an organizer decision; acceptance never schedules or publishes a talk."""
    try:
        result = ctx.obj["inbox"].review(receipt, status)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, default=str, indent=2))


@inbox.command("purge")
@click.pass_context
def inbox_purge(ctx):
    """Remove expired previews, credentials and submission records."""
    ctx.obj["inbox"].maintenance()
    click.echo("Expired private records removed.")


@inbox.command("revoke-access")
@click.argument("credential_file", type=click.Path(exists=True, dir_okay=False))
@click.pass_context
def revoke_access(ctx, credential_file):
    """Revoke a participant credential without printing it."""
    try:
        path = Path(credential_file)
        if path.stat().st_size > 1024:
            raise ValueError("Invalid credential file")
        ctx.obj["inbox"].revoke(path.read_text().strip())
    except (OSError, ValueError) as exc:
        raise click.ClickException("Could not revoke this participant credential.") from exc
    click.echo("Participant access and pending previews revoked.")


@main.command("query")
@click.argument("payload")
@click.pass_context
def raw_query(ctx, payload):
    """Execute the same JSON request accepted by MCP and A2A."""
    try:
        parsed = json.loads(payload)
    except ValueError as exc:
        raise click.ClickException("Payload must be JSON.") from exc
    dispatch(ctx, parsed)


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8000, type=click.IntRange(1, 65535))
def serve(host, port):
    """Run the combined HTTP, MCP and A2A server (install [server])."""
    try:
        import uvicorn
        from .server import create_app
    except ImportError as exc:
        raise click.ClickException("Install agenteng[server] for hosted transports.") from exc
    uvicorn.run(create_app(), host=host, port=port)


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
