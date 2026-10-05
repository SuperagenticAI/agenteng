"""CLI output mode helpers and Agent Engineering palette."""

from __future__ import annotations

import os
import sys

from rich.console import Console
from rich.theme import Theme

BLUE = "#357bff"
VIOLET = "#8c1aff"
MAGENTA = "#e020b8"

THEME = Theme(
    {
        "ae.blue": BLUE,
        "ae.violet": VIOLET,
        "ae.magenta": MAGENTA,
        "ae.title": f"bold {BLUE}",
        "ae.accent": VIOLET,
        "ae.meta": "dim",
        "ae.ok": "bold green",
        "ae.warn": "bold yellow",
        "ae.err": "bold red",
        "ae.sold": "bold red",
        "ae.price": f"bold {MAGENTA}",
    }
)


def display_text(value: str | None) -> str:
    """Human-facing text: replace em dashes without changing source data."""
    if not value:
        return ""
    return value.replace("\u2014", " - ").replace("\u2013", "-")


def stdout_is_tty() -> bool:
    return sys.stdout.isatty()


def stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def use_json(ctx) -> bool:
    """JSON for agents: --json, AGENTENG_OUTPUT=json, or non-TTY stdout."""
    if ctx.obj.get("as_json"):
        return True
    if os.environ.get("AGENTENG_OUTPUT", "").strip().lower() == "json":
        return True
    return not stdout_is_tty()


def make_console(*, record: bool = False, width: int | None = None) -> Console:
    # soft_wrap must stay False: True crops long Panel lines instead of wrapping.
    kwargs: dict = {"theme": THEME, "highlight": False, "soft_wrap": False}
    if record:
        kwargs["record"] = True
        kwargs["force_terminal"] = True
        kwargs["width"] = width or 88
    return Console(**kwargs)
