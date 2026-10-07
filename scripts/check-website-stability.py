#!/usr/bin/env python3
"""Exercise the real catalogue exporter against a temporary public-source copy."""

from pathlib import Path
import tempfile
import shutil
import subprocess
import json
import argparse

parser = argparse.ArgumentParser(
    description="Verify full website export identity across agenda reordering and duplicate IDs."
)
parser.add_argument(
    "website", type=Path, help="Conference website checkout with installed Node dependencies"
)
website = parser.parse_args().website.resolve()
exporter = Path(__file__).resolve().with_name("export-website.mjs")
with tempfile.TemporaryDirectory(prefix="agenteng-export-stability-") as directory:
    root = Path(directory)
    shutil.copytree(website / "src", root / "src")
    shutil.copytree(website / "public", root / "public")
    shutil.copy2(website / "package.json", root / "package.json")
    (root / "node_modules").symlink_to(website / "node_modules", target_is_directory=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Export test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "Export test fixture",
        ],
        check=True,
    )

    def export(name, ok=True):
        result = subprocess.run(
            ["node", str(exporter), str(root), str(root / name)], capture_output=True, text=True
        )
        assert (result.returncode == 0) == ok, result.stderr
        return json.loads((root / name).read_text()) if ok else result

    baseline = export("before.json")
    p = root / "src/data/agenda.ts"
    original = p.read_text()
    start = original.index("export const agenda: AgendaSlot[] = [")
    end = original.index("\n];", start)
    block = original[start:end]
    lines = block.splitlines()
    slots = [line for line in lines if line.strip().startswith("{ id:")]
    p.write_text(original[:start] + lines[0] + "\n" + "\n".join(reversed(slots)) + original[end:])
    reordered = export("after.json")
    assert {s["id"]: s for s in baseline["sessions"]} == {s["id"]: s for s in reordered["sessions"]}
    assert {s["id"]: s for s in baseline["sources"]} == {s["id"]: s for s in reordered["sources"]}
    p.write_text(original.replace('agenteng-london-2026-1"', 'agenteng-london-2026-0"', 1))
    rejected = export("bad.json", False)
    assert "unique, stable public id" in rejected.stderr
    assert not (root / "bad.json").exists()
    print(
        "Full exporter stability check passed: running-order reversal retains session/source IDs; duplicate IDs fail before writing."
    )
