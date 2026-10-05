"""Local-only personal agenda bookmarks (no server, no sync)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    """Return the AgentEng config directory, creating it when needed."""
    override = os.environ.get("AGENTENG_CONFIG_DIR")
    if override:
        path = Path(override).expanduser()
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
        path = root / "agenteng"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bookmarks_path() -> Path:
    return config_dir() / "bookmarks.json"


def load_bookmarks() -> list[str]:
    path = bookmarks_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    rows = data.get("session_ids") or []
    if not isinstance(rows, list):
        return []
    return [str(item) for item in rows if isinstance(item, str) and item]


def save_bookmarks(session_ids: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in session_ids:
        if item and item not in seen:
            unique.append(item)
            seen.add(item)
    path = bookmarks_path()
    path.write_text(
        json.dumps({"session_ids": unique}, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return unique


def add_bookmark(session_id: str) -> list[str]:
    rows = load_bookmarks()
    if session_id not in rows:
        rows.append(session_id)
    return save_bookmarks(rows)


def remove_bookmark(session_id: str) -> list[str]:
    return save_bookmarks([item for item in load_bookmarks() if item != session_id])
