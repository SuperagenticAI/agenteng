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
    # Bookmarks and ACP agent logs are personal; a new folder is private to the user.
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
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
    # Create the file 0600 from the start, then replace atomically: no window in
    # which another local user could read it.
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(json.dumps({"session_ids": unique}, indent=2) + "\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
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
