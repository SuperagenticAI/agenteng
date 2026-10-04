#!/usr/bin/env python3
"""Stage the installer and release artifacts for the website's public directory."""

import argparse
import hashlib
import shutil
from pathlib import Path

from agenteng import __version__
from agenteng.config import Settings
from agenteng.discovery import llms_text
from agenteng.models import Request
from agenteng.service import Service

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=root / "dist" / "website-public")
args = parser.parse_args()

wheel = root / "dist" / f"agenteng_hq-{__version__}-py3-none-any.whl"
if not wheel.is_file():
    parser.error("Build the release wheel first: uv build")
installer = root / "src/agenteng/data/install.sh"
if f"VERSION={__version__}\n" not in installer.read_text():
    parser.error("Installer version differs from package version")
release = args.output / "releases" / __version__
release.mkdir(parents=True, exist_ok=True)
shutil.copy2(wheel, release / wheel.name)
shutil.copy2(installer, args.output / "install.sh")
checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
(release / "SHA256SUMS").write_text(f"{checksum}  {wheel.name}\n")
service = Service(Settings())
(args.output / "agenteng-agent-guide.txt").write_text(llms_text(service))
(args.output / "agenteng-events.json").write_text(
    service.lookup(Request(operation="discover")).model_dump_json(indent=2) + "\n"
)
(args.output / "agenteng-tools.json").write_text(
    service.tool_directory.model_dump_json(indent=2) + "\n"
)
print(
    f"Staged installer, wheel, checksum, agent guide, event feed and tool directory in {args.output}"
)
