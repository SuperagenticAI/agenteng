"""About, HQ, venue-screen snapshot and talk bingo. Local, model-free, published data only."""

from __future__ import annotations

import html
import random
import re
import secrets
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from .tool_directory import DISCIPLINES

if TYPE_CHECKING:
    from .models import Request, Result
    from .service import Service

SITE = "https://agentengineering.world"
INSTALL = "curl -fsSL https://agentengineering.world/install.sh | sh"
UV_INSTALL = "uv tool install agenteng"

# Bingo squares: a short label and the pattern that must appear in the event's
# published talk titles, abstracts or agenda. A term with no evidence is never
# placed on a card, so every square points back to a published session.
BINGO_TERMS: tuple[tuple[str, str], ...] = (
    ("ACP", r"\bACP\b"),
    ("MCP", r"\bMCP\b"),
    ("WebMCP", r"\bWebMCP\b"),
    ("CLI", r"\bCLI\b"),
    ("Agent API", r"\bagent API\b"),
    ("LLMs", r"\bLLMs?\b"),
    ("Coding agents", r"\bcoding agents?\b"),
    ("Agentic coding", r"\bagentic coding\b"),
    ("Long-running agents", r"\blong-running\b"),
    ("Inference", r"\binference\b"),
    ("Caching", r"\bcaching\b"),
    ("Scheduling", r"\bscheduling\b"),
    ("Throughput", r"\bthroughput\b"),
    ("Serving", r"\bserving\b"),
    ("Metrics", r"\bmetrics\b"),
    ("Constraints", r"\bconstraints?\b"),
    ("Optimization", r"\boptimi[sz](?:e|ation|ing)\b"),
    ("Feedback loop", r"\bfeedback\b"),
    ("Software factory", r"\bsoftware[- ]factor(?:y|ies)\b"),
    ("Randomness", r"\brandomness\b"),
    ("Herding agents", r"\bherding\b"),
    ("Code review", r"\breview(?:ing)?\b"),
    ("Planning", r"\bplanning\b"),
    ("Testing", r"\btesting\b"),
    ("Is coding solved?", r"\bcoding is solved\b"),
    ("Skynet", r"\bSkynet\b"),
    ("Voice agents", r"\bvoice agents?\b"),
    ("Debugging", r"\bdebugging\b"),
    ("Browser use", r"\bbrowser use\b"),
    ("Scraping", r"\bscraping\b"),
    ("Tool selection", r"\bselection\b"),
    ("Harness", r"\bharness(?:es)?\b"),
    ("Security", r"\bsecurity\b"),
    ("AI-native", r"\bAI-Native\b"),
    ("Memory", r"\bmemory\b"),
    ("Context window", r"\bcontext window\b"),
    ("Right info, right time", r"\bright information at the right time\b"),
    ("Grade harder", r"\bgrade harder\b"),
    ("Evals", r"\beval(?:s|uat(?:e|ion|ing))?\b"),
    ("Self-improving", r"\bself-improving\b"),
    ("RLM", r"\bRLM\b"),
    ("Swarm", r"\bswarm\b"),
    ("Latency", r"\blatency\b"),
    ("Live traffic", r"\blive traffic\b"),
    ("Fresh context", r"\bfresh context\b"),
    ("Networking break", r"\bnetworking break\b"),
    ("Tea and pastries", r"\bpastries\b"),
)
FREE = "FREE"
COLUMNS = "ABCDE"


def local_now(service: Service, request: Request, tz: str) -> datetime:
    zone = ZoneInfo(tz)
    if request.at is not None:
        at = request.at
        return (at.replace(tzinfo=zone) if at.utcoffset() is None else at).astimezone(zone)
    return service.clock().astimezone(zone)


def about(service: Service, request: Request) -> Result:
    record = service.catalogue.about
    origin = service.settings.public_url
    connect = {
        "install": INSTALL,
        "install_uv": UV_INSTALL,
        "mcp_url": origin + "/mcp/",
        "agent_card_url": origin + "/.well-known/agent-card.json",
        "http_query_url": origin + "/v1/query",
        "llms_txt_url": origin + "/llms.txt",
        "local_mcp": "agenteng mcp",
        "connect_commands": [
            f"ae connect {c}" for c in ("claude-code", "codex", "cursor", "generic")
        ],
    }
    hq = service.catalogue.hq
    data: dict = {
        "name": "Agent Engineering HQ",
        "summary": hq.summary if hq else None,
        "definition": record.definition if record else None,
        "cities": list(dict.fromkeys(e.city for e in service.catalogue.events)),
        "organiser": record.organiser.model_dump(mode="json")
        if record and record.organiser
        else None,
        "chair": record.chair.model_dump(mode="json") if record and record.chair else None,
        "contact_email": record.contact_email if record else None,
        "links": {
            "website": SITE + "/",
            "hq": SITE + "/agent-engineering-hq",
            "london": SITE + "/london",
            "san_francisco": SITE + "/san-francisco",
            "code_of_conduct": SITE + "/code-of-conduct",
        },
        "connect": connect,
    }
    source_ids = (record.source_ids if record else []) + ["hq"]
    if request.section:
        if data.get(request.section) is None:
            return service.result(
                f"No published {request.section} information in this catalogue.",
                status="not_found",
            )
        data = {"section": request.section, request.section: data[request.section]}
        source_ids = {"connect": [], "chair": source_ids[:1], "organiser": source_ids[:1]}[
            request.section
        ]
    answer = (
        "Agent Engineering HQ runs AgentEng conferences and technical events in "
        + " and ".join(dict.fromkeys(e.city for e in service.catalogue.events))
        + "."
    )
    return service.result(answer, data, [s for s in source_ids if s in service.sources])


def hq(service: Service, request: Request) -> Result:
    record = service.catalogue.hq
    if not record:
        return service.result(
            "No Agent Engineering HQ content in this catalogue.", status="not_found"
        )
    data = record.model_dump(mode="json")
    data.pop("source_ids", None)
    sources = {
        "manifesto": "hq-manifesto",
        "mindset": "hq-mindset",
        "reading": "hq-further-reading",
    }
    if request.section:
        key = "further_reading" if request.section == "reading" else request.section
        data = {
            "section": request.section,
            "url": data["url"],
            key: data[key],
            **(
                {"further_reading_intro": data["further_reading_intro"]}
                if request.section == "reading"
                else {}
            ),
        }
        ids = [sources[request.section]]
    else:
        ids = list(record.source_ids)
    return service.result(
        "Agent Engineering HQ: manifesto, mindset and further reading from the website.",
        data,
        [i for i in ids if i in service.sources],
    )


def live(service: Service, request: Request) -> Result:
    """One venue-screen frame: what is on, what is next, and the clock."""
    event_id = service.default_live_event_id(request)
    if not event_id:
        return service.result(
            "Choose an event_id with a published timed agenda.", status="unavailable"
        )
    event = service.events[event_id]
    now = local_now(service, request, event.timezone)
    timed = sorted(
        (s for s in service.catalogue.sessions if s.event_id == event_id and s.start and s.end),
        key=lambda s: s.start,
    )
    if not timed:
        return service.result(
            f"{event.title} has no published timed agenda yet.",
            {"event_id": event_id, "as_of": now.isoformat(), "current": None, "next": None},
            event.source_ids,
            status="not_found",
        )
    current = next((s for s in timed if s.start <= now < s.end), None)
    later = [s for s in timed if s.start > now]
    upcoming = later[0] if later else None
    if current:
        phase = "during"
    elif now < timed[0].start:
        phase = "before"
    elif upcoming:
        phase = "between"
    else:
        phase = "after"
    talk = service.talk_payload
    current_data = None
    if current:
        total = (current.end - current.start).total_seconds()
        elapsed = (now - current.start).total_seconds()
        current_data = {
            **talk(current),
            "elapsed_seconds": int(elapsed),
            "remaining_seconds": int(total - elapsed),
            "progress": round(elapsed / total, 4) if total else 1.0,
        }
    next_data = None
    if upcoming:
        next_data = {
            **talk(upcoming),
            "starts_in_seconds": int((upcoming.start - now).total_seconds()),
        }
    data = {
        "event_id": event_id,
        "event": {
            "title": event.title,
            "city": event.city,
            "venue": event.venue,
            "track": event.track,
            "timezone": event.timezone,
            "date": event.date,
            "start": event.start.isoformat() if event.start else None,
            "end": event.end.isoformat() if event.end else None,
        },
        "as_of": now.isoformat(),
        "phase": phase,
        "current": current_data,
        "next": next_data,
        "later": [
            {"id": s.id, "title": s.title, "kind": s.kind, "start": s.start.isoformat()}
            for s in later[1:4]
        ],
    }
    if current and upcoming:
        answer = f"Now: {current.title}. Next: {upcoming.title}."
    elif current:
        answer = f"Now: {current.title}. Last session of the day."
    elif upcoming:
        answer = f"Next: {upcoming.title}."
    else:
        answer = "The published agenda has finished."
    ids = [*(current.source_ids if current else []), *(upcoming.source_ids if upcoming else [])]
    return service.result(answer, data, ids or event.source_ids)


def bingo_pool(service: Service, event_id: str) -> list[dict]:
    speakers = service.speaker_map()
    texts: dict[str, str] = {}
    for session in service.catalogue.sessions:
        if session.event_id != event_id:
            continue
        speaker = speakers.get(session.speaker_id) if session.speaker_id else None
        texts[session.id] = " ".join(
            filter(
                None,
                [
                    session.title,
                    speaker.talk_title if speaker else None,
                    speaker.abstract if speaker else None,
                ],
            )
        )
    pool = []
    for label, pattern in BINGO_TERMS:
        hits = [sid for sid, text in texts.items() if re.search(pattern, text, re.IGNORECASE)]
        if hits:
            pool.append({"label": label, "session_ids": hits})
    known = {p["label"].split()[0].casefold().rstrip("s") for p in pool}
    disciplines = sorted(
        {d for s in speakers.values() if event_id in s.event_ids for d in s.disciplines}
    )
    for discipline in disciplines:
        title = DISCIPLINES.get(discipline)
        if title and title.split()[0].casefold().rstrip("s") not in known:
            sessions = [
                s.id
                for s in service.catalogue.sessions
                if s.event_id == event_id
                and s.speaker_id
                and discipline in speakers[s.speaker_id].disciplines
            ]
            pool.append({"label": title, "session_ids": sessions})
    return sorted(pool, key=lambda p: p["label"].casefold())


def bingo(service: Service, request: Request) -> Result:
    event_id = service.default_live_event_id(request) or request.event_id
    if not event_id:
        return service.result("Choose an event_id with published talks.", status="unavailable")
    event = service.events[event_id]
    size = request.size
    needed = size * size - (1 if size == 5 else 0)
    pool = bingo_pool(service, event_id)
    if len(pool) < needed:
        return service.result(
            f"{event.title} publishes {len(pool)} bingo terms; a {size}x{size} card needs {needed}. "
            + ("Try --size 4, or " if size == 5 else "Try ")
            + "an event with a fuller published agenda.",
            {"event_id": event_id, "terms": len(pool), "needed": needed},
            event.source_ids,
            status="unavailable",
        )
    seed = request.seed if request.seed is not None else secrets.randbelow(1_000_000)
    picks = random.Random(f"{event_id}:{size}:{seed}").sample(pool, needed)
    squares = [{"label": p["label"], "session_ids": p["session_ids"]} for p in picks]
    if size == 5:
        squares.insert(12, {"label": FREE, "session_ids": [], "free": True})
    grid = [squares[r * size : (r + 1) * size] for r in range(size)]
    card = {
        "event_id": event_id,
        "event_title": event.title,
        "size": size,
        "seed": seed,
        "card_id": f"{event_id}/{size}x{size}/{seed}",
        "command": f"ae bingo --event {event_id} --size {size} --seed {seed}",
        "grid": [[cell["label"] for cell in row] for row in grid],
        "squares": squares,
        "pool_size": len(pool),
        "rules": "Mark a square when a speaker says or shows it. Five in a row, column or "
        "diagonal wins (four on a 4x4). Local only: nothing is sent anywhere.",
    }
    artifact = None
    if request.format == "text":
        artifact = bingo_text(card)
    elif request.format == "svg":
        artifact = bingo_svg(card)
    elif request.format == "html":
        artifact = bingo_html(card)
    ids = list(
        dict.fromkeys(
            i
            for s in squares
            for sid in s["session_ids"]
            for i in service.session_map()[sid].source_ids
        )
    )
    return service.result(
        f"Talk bingo card {card['card_id']} with {needed} published terms.",
        card,
        ids[:12] or event.source_ids,
        artifact=artifact,
    )


def winning_lines(marked: set[tuple[int, int]], size: int) -> list[str]:
    lines = []
    for r in range(size):
        if all((r, c) in marked for c in range(size)):
            lines.append(f"row {r + 1}")
    for c in range(size):
        if all((r, c) in marked for r in range(size)):
            lines.append(f"column {COLUMNS[c]}")
    if all((i, i) in marked for i in range(size)):
        lines.append("diagonal")
    if all((i, size - 1 - i) in marked for i in range(size)):
        lines.append("anti-diagonal")
    return lines


def wrap(label: str, width: int) -> list[str]:
    lines: list[str] = []
    for word in label.split():
        if lines and len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines or [""]


def bingo_text(card: dict, marked: set[tuple[int, int]] | None = None) -> str:
    size, cell = card["size"], 14
    marked = marked or set()
    rule = "+" + "+".join(["-" * cell] * size) + "+"
    out = [
        f"AGENTENG TALK BINGO  {card['event_title']}",
        f"Card {card['card_id']}",
        "",
        "   " + "".join(f" {COLUMNS[c]:^{cell}}" for c in range(size)),
        "   " + rule,
    ]
    for r, row in enumerate(card["grid"]):
        wrapped = [wrap(label, cell - 2) for label in row]
        height = max(2, max(len(w) for w in wrapped))
        for line in range(height):
            parts = []
            for c, w in enumerate(wrapped):
                text = w[line] if line < len(w) else ""
                if (r, c) in marked and line == height - 1:
                    text = "[X]"
                parts.append(f"{text:^{cell}}")
            label = f"{r + 1:>2} " if line == 0 else "   "
            out.append(label + "|" + "|".join(parts) + "|")
        out.append("   " + rule)
    out += ["", card["rules"], f"Same card again: {card['command']}", ""]
    return "\n".join(out)


def bingo_svg(card: dict) -> str:
    size = card["size"]
    cell, pad, top = 150, 30, 120
    width = pad * 2 + cell * size
    height = top + cell * size + 110
    esc = html.escape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Inter, Helvetica, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        '<defs><linearGradient id="ae" x1="0" x2="1"><stop offset="0" stop-color="#357bff"/>'
        '<stop offset="0.5" stop-color="#8c1aff"/><stop offset="1" stop-color="#e020b8"/>'
        "</linearGradient></defs>",
        f'<rect x="0" y="0" width="{width}" height="8" fill="url(#ae)"/>',
        f'<text x="{width / 2}" y="58" text-anchor="middle" font-size="34" font-weight="800" '
        f'fill="#111">AgentEng Talk Bingo</text>',
        f'<text x="{width / 2}" y="92" text-anchor="middle" font-size="16" fill="#555">'
        f"{esc(card['event_title'])}</text>",
    ]
    for r, row in enumerate(card["grid"]):
        for c, label in enumerate(row):
            x, y = pad + c * cell, top + r * cell
            free = label == FREE
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{"url(#ae)" if free else "#ffffff"}" stroke="#8c1aff" stroke-width="2"/>'
            )
            lines = wrap(label, 13)
            first = y + cell / 2 - (len(lines) - 1) * 11
            for i, line in enumerate(lines):
                parts.append(
                    f'<text x="{x + cell / 2}" y="{first + i * 22 + 6}" text-anchor="middle" '
                    f'font-size="{22 if free else 17}" font-weight="{800 if free else 600}" '
                    f'fill="{"#ffffff" if free else "#111"}">{esc(line)}</text>'
                )
    foot = top + cell * size
    rules = wrap(card["rules"], 12 * size + 20)
    for i, line in enumerate(rules):
        parts.append(
            f'<text x="{pad}" y="{foot + 30 + i * 18}" font-size="13" fill="#555">{esc(line)}</text>'
        )
    parts += [
        f'<text x="{pad}" y="{foot + 36 + len(rules) * 18}" font-size="12" fill="#555" '
        f'font-family="monospace">Card {esc(card["card_id"])}  ·  {esc(card["command"])}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def bingo_html(card: dict) -> str:
    title = html.escape(f"AgentEng Talk Bingo, {card['event_title']}")
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title>"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>body{margin:0;display:flex;justify-content:center;background:#f4f4f8}"
        "main{margin:24px;background:#fff;box-shadow:0 2px 16px #0002}"
        "svg{display:block;max-width:100%;height:auto}"
        "@media print{body{background:#fff}main{margin:0;box-shadow:none}}"
        "@page{margin:12mm}</style></head><body><main>\n"
        + bingo_svg(card)
        + "</main></body></html>\n"
    )


def shift_clock(at: datetime | None) -> timedelta:
    """Offset that makes a demo --at time advance in real time on a live screen."""
    if at is None:
        return timedelta(0)
    now = datetime.now(at.tzinfo) if at.tzinfo else datetime.now()
    return at - now
