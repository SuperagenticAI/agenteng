#!/usr/bin/env python3
"""Check literal website commands against the real Click CLI and run public lookups."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

import click
from click.testing import CliRunner

from agenteng.cli import main

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("website", type=Path, help="Website checkout with Node dependencies installed")
website = parser.parse_args().website.resolve()
rows = json.loads(
    subprocess.check_output(
        ["node", str(Path(__file__).with_name("list-website-commands.mjs")), str(website)],
        text=True,
    )
)
errors = []
executed = 0
with tempfile.TemporaryDirectory(prefix="agenteng-command-check-") as temporary:
    runner = CliRunner(env={"AGENTENG_OUTPUT": "json", "AGENTENG_CONFIG_DIR": temporary})
    for row in rows:
        command = row["command"]
        argv = shlex.split(command)[1:]
        if any(flag in argv for flag in ["--help", "-h"]):
            outcome = runner.invoke(main, argv)
            if outcome.exit_code:
                errors.append(f"{command}: {outcome.output.strip()}")
            else:
                executed += 1
            continue
        current = main
        remaining = argv
        parent = None
        try:
            while True:
                ctx = current.make_context(current.name, remaining, parent=parent)
                if not isinstance(current, click.Group):
                    break
                group_args = ctx._protected_args + ctx.args
                if not group_args:
                    break
                _, current, remaining = current.resolve_command(ctx, group_args)
                parent = ctx
        except click.exceptions.Exit as exc:
            if exc.exit_code:
                errors.append(f"{command}: exits {exc.exit_code}")
                continue
        except click.ClickException as exc:
            errors.append(f"{command}: {exc.format_message()} ({', '.join(row['locations'])})")
            continue
        # Server loops and coding sessions are parsed, never launched by this check.
        if argv and argv[0] in {"serve", "mcp", "code"}:
            continue
        outcome = runner.invoke(main, argv)
        if outcome.exit_code:
            errors.append(f"{command}: {outcome.output.strip()} ({', '.join(row['locations'])})")
        else:
            executed += 1
if errors:
    raise SystemExit("\n".join(errors))
print(
    f"Verified {len(rows)} distinct website command literals; {executed} public lookups/setup commands executed successfully. Server/coding commands were parsed without launching them."
)
