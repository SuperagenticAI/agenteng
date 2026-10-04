"""Standards-compliant UTC calendar export; never invent missing session times."""

from datetime import UTC, datetime

from .models import Event, Session


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold(line: str) -> str:
    chunks, current = [], ""
    for char in line:
        if len((current + char).encode()) > 75:
            chunks.append(current)
            current = " "
        current += char
    return "\r\n".join([*chunks, current])


def calendar(event: Event, sessions: list[Session], now: datetime) -> str:
    def stamp(value):
        return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AgentEng HQ//Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    # An event without an exact day/time cannot be exported as a timed event.
    rows = (
        [(event.id, event.title, event.start, event.end)]
        if not sessions
        else [(s.id, s.title, s.start, s.end) for s in sessions]
    )
    for uid, title, start, end in rows:
        if start is None or end is None:
            continue
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}@agentengineering.world",
                "DTSTAMP:" + stamp(now),
                "DTSTART:" + stamp(start),
                "DTEND:" + stamp(end),
                "SUMMARY:" + escape(title),
                "LOCATION:" + escape(event.venue),
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(map(fold, lines)) + "\r\n"
