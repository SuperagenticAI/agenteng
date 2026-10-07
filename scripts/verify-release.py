#!/usr/bin/env python3
"""Verify a built wheel offline in a separate, core-only Python environment.

Copies the declared dependency closure from the active environment; installs
only the release wheel. This checks packaging and optional-dependency isolation,
not remote package availability or Linux container compatibility.
"""

import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import venv

from packaging.requirements import Requirement

from agenteng import __version__

root = Path(__file__).resolve().parents[1]
wheel = root / "dist" / f"agenteng-{__version__}-py3-none-any.whl"
if not wheel.exists():
    raise SystemExit("Build the release wheel first.")
with tempfile.TemporaryDirectory(prefix="agenteng-release-") as temporary:
    target = Path(temporary)
    environment = target / "env"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    python = environment / "bin/python"
    site = Path(
        subprocess.check_output(
            [str(python), "-c", 'import sysconfig; print(sysconfig.get_paths()["purelib"])'],
            text=True,
        ).strip()
    )
    # Derive core dependencies from the release wheel, not a second handwritten list.
    import zipfile
    from email.parser import BytesParser

    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
        package_metadata = BytesParser().parsebytes(archive.read(metadata_name))
    queue = []
    for raw in package_metadata.get_all("Requires-Dist", []):
        requirement = Requirement(raw)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            queue.append(requirement.name)
    copied = set()
    while queue:
        name = queue.pop()
        if name in copied:
            continue
        dist = metadata.distribution(name)
        copied.add(name)
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                queue.append(requirement.name)
        for file in dist.files or []:
            if ".." in file.parts:
                continue
            source = dist.locate_file(file)
            if source.is_file():
                destination = site / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    subprocess.run(
        ["uv", "pip", "install", "--offline", "--no-deps", "--python", str(python), str(wheel)],
        check=True,
        env={**os.environ, "UV_CACHE_DIR": str(target / "cache")},
    )
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            """
import importlib.util
from importlib.metadata import metadata, version
assert all(importlib.util.find_spec(name) is None for name in ['mcp', 'a2a', 'pydantic_monty'])
import agenteng
assert agenteng.__version__ == __import__("sys").argv[1]
assert metadata("agenteng")["Name"] == "agenteng"
assert version("agenteng") == agenteng.__version__
""",
            __version__,
        ],
        check=True,
        cwd=target,
    )
    output = subprocess.check_output(
        [str(environment / "bin/agenteng"), "--json", "events"],
        cwd=target,
        env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "AGENTENG_CATALOGUE"}},
        text=True,
    )
    result = json.loads(output)
    assert result["engine"] == "lookup" and len(result["data"]) == 11
    tools_output = subprocess.check_output(
        [str(environment / "bin/agenteng"), "--json", "tools", "--limit", "100", "--status", "all"],
        cwd=target,
        env={k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "AGENTENG_CATALOGUE"}},
        text=True,
    )
    tools = json.loads(tools_output)
    assert tools["engine"] == "lookup" and tools["data"]["total"] == 456
    assert tools["data"]["directory"]["source"]["entry_count"] == 461
    assert tools["data"]["next_offset"] == 100
    agenda_output = subprocess.check_output(
        [
            str(environment / "bin/agenteng"),
            "--json",
            "query",
            '{"operation":"agenda","event_id":"agenteng-london-2026"}',
        ],
        cwd=target,
        env={
            k: v
            for k, v in os.environ.items()
            if k not in {"PYTHONPATH", "AGENTENG_CATALOGUE", "AGENTENG_ENABLE_INTAKE"}
        },
        text=True,
    )
    assert json.loads(agenda_output)["status"] == "ok"
    print(
        "Release wheel: offline CLI, events, tool directory and public agenda work without MCP, A2A or Monty."
    )
