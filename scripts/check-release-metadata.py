#!/usr/bin/env python3
"""Check release versions without importing or executing package/installer code."""

import argparse
import ast
from pathlib import Path
import re
import tomllib

RELEASE_TAG = re.compile(r"v\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?")
ROOT = Path(__file__).resolve().parents[1]


def release_metadata_errors(root: Path, tag: str | None = None) -> list[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    version = project["version"]
    errors = []
    if project["name"] != "agenteng":
        errors.append("Package name must be agenteng.")
    if not isinstance(version, str) or not RELEASE_TAG.fullmatch("v" + version):
        errors.append("Package version must be a canonical three-component release version.")
    if tag is not None and (not RELEASE_TAG.fullmatch(tag) or tag != "v" + version):
        errors.append(f"Release tag must exactly match v + project.version (expected v{version}).")
    if project.get("scripts", {}).get("agenteng") != "agenteng.cli:main":
        errors.append("Unexpected agenteng CLI entry point.")
    module = ast.parse((root / "src/agenteng/__init__.py").read_text())
    versions = [
        node.value.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    ]
    if versions != [version]:
        errors.append("Package __version__ differs from project.version.")
    lock = tomllib.loads((root / "uv.lock").read_text())
    if [p.get("version") for p in lock["package"] if p["name"] == "agenteng"] != [version]:
        errors.append("uv.lock project version differs from project.version.")
    installer = (root / "src/agenteng/data/install.sh").read_text()
    if "uv tool install" not in installer:
        errors.append("Installer must use uv tool install from PyPI.")
    if "agenteng" not in installer:
        errors.append("Installer must install the agenteng package.")
    if re.search(r"^VERSION=", installer, re.MULTILINE):
        errors.append("Installer must not hardcode VERSION; install latest from PyPI.")
    if "agentengineering.world/releases/" in installer:
        errors.append("Installer must not download wheels from the website releases mirror.")
    if "SuperQode" in installer or "superqode" in installer:
        errors.append("Installer must not mention SuperQode.")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected v-prefixed release tag")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        errors = release_metadata_errors(args.root, args.tag)
    except (OSError, KeyError, ValueError, TypeError, SyntaxError):
        parser.exit(1, "Cannot validate release metadata; check the required source files.\n")
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    print("Release metadata is consistent.")


if __name__ == "__main__":
    main()
