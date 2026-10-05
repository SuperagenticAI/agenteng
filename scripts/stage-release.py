#!/usr/bin/env python3
"""Stage the installer and discovery feeds for the website's public directory."""

import argparse
import shutil
from pathlib import Path

from agenteng.config import Settings
from agenteng.discovery import llms_text
from agenteng.models import Request
from agenteng.service import Service

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=root / "dist" / "website-public")
args = parser.parse_args()

installer = root / "src/agenteng/data/install.sh"
text = installer.read_text()
if "uv tool install" not in text or "agenteng" not in text:
    parser.error("Installer must install agenteng from PyPI via uv tool install")
if "agentengineering.world/releases/" in text:
    parser.error("Installer must not download wheels from the website releases mirror")
args.output.mkdir(parents=True, exist_ok=True)
shutil.copy2(installer, args.output / "install.sh")
service = Service(Settings())
(args.output / "agenteng-agent-guide.txt").write_text(llms_text(service))
(args.output / "agenteng-events.json").write_text(
    service.lookup(Request(operation="discover")).model_dump_json(indent=2) + "\n"
)
(args.output / "agenteng-tools.json").write_text(
    service.tool_directory.model_dump_json(indent=2) + "\n"
)
print(f"Staged installer, agent guide, event feed and tool directory in {args.output}")
