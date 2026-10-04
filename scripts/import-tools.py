#!/usr/bin/env python3
"""Normalize a local SuperRadar snapshot without executing or fetching source content."""

import argparse
from pathlib import Path

from agenteng.tool_import import normalize_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", type=Path, help="Local superradar-tools.json from a pinned checkout"
    )
    parser.add_argument("--commit", required=True, help="Full source commit SHA")
    parser.add_argument("--output", type=Path, default=Path("src/agenteng/data/tools.json"))
    args = parser.parse_args()
    try:
        # Read bounded input; do not trust the source file's reported size.
        with args.source.open("rb") as file:
            content = file.read(8 * 1024 * 1024 + 1)
        directory = normalize_snapshot(content, args.commit)
        payload = directory.model_dump_json(indent=2) + "\n"
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(f"Import rejected; output unchanged: {type(exc).__name__}")
    # Validate everything first; replace the bundle atomically only on success.
    import os
    import tempfile

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(payload)
        temporary.chmod(0o644)
        os.replace(temporary, args.output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(
        f"Imported {directory.source.entry_count} source entries into {len(directory.tools)} listings."
    )


if __name__ == "__main__":
    main()
