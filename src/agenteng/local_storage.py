"""Private local directory for optional developer-agent stderr logs."""

from __future__ import annotations

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
    # Developer-agent logs can contain prompt text; create a private folder.
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path
