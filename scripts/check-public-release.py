#!/usr/bin/env python3
"""Check Git candidates and release archives for private files and obvious leaks.

This is a focused release guard, not a complete secret scanner. Findings never
print matched credential values. Review the diff as well as the archives.
"""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile

PRIVATE_NAMES = {"PLAN.md", "RLM-DESIGN.md", "IMPLEMENTATION.md"}
PRIVATE_PARTS = {
    ".private",
    ".agenteng",
    ".git",
    ".venv",
    ".cache",
    "__pycache__",
    "proposal-drafts",
    "submissions",
    "node_modules",
    ".aws",
    ".azure",
    ".gcloud",
}
PATTERNS = {
    "participant credential": re.compile(r"\bae_participant_[A-Za-z0-9_-]{40,}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub credential": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"
    ),
    "model credential": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "local home path": re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/"),
}


def protected(path: str) -> bool:
    value = PurePosixPath(path)
    name = value.name
    return (
        value.is_absolute()
        or ".." in value.parts
        or bool(PRIVATE_PARTS.intersection(value.parts))
        or name in PRIVATE_NAMES
        or name == ".env"
        or (name.startswith("participant-access") and name.endswith(".txt"))
        or (name.startswith(".env.") and name != ".env.example")
        or name.endswith(
            (
                ".pem",
                ".key",
                ".p12",
                ".pfx",
                ".pyc",
                ".credentials.json",
                ".log",
                ".sqlite",
                ".sqlite3",
                ".db",
                ".db-journal",
                ".db-wal",
                ".db-shm",
                ".sqlite-journal",
                ".sqlite-wal",
                ".sqlite-shm",
                ".sqlite3-journal",
                ".sqlite3-wal",
                ".sqlite3-shm",
            )
        )
        or (name.startswith("service-account") and name.endswith(".json"))
        or bool(re.fullmatch(r"(?:attendees|members|contacts)(?:[-_].*)?\.csv", name))
        or (
            len(value.parts) == 1
            and bool(re.fullmatch(r"(?:draft|talk|proposal(?:-.*)?)\.(?:json|md)", name))
        )
    )


def inspect(path: str, data: bytes) -> list[str]:
    errors = ["private file: " + path] if protected(path) else []
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return errors
    for label, pattern in PATTERNS.items():
        match = pattern.search(content)
        if match:
            line = content[: match.start()].count("\n") + 1
            errors.append(f"{path}:{line}: {label}")
    return errors


def source_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("Run the source audit from a Git checkout.")
    return sorted(set(result.stdout.decode().rstrip("\0").split("\0")) - {""})


def archive_errors(path: Path) -> list[str]:
    errors = []
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if not member.is_dir():
                    errors.extend(inspect(member.filename, archive.read(member)))
    else:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                parts = PurePosixPath(member.name).parts
                relative = "/".join(parts[1:])
                if member.issym() or member.islnk():
                    errors.append("archive link not allowed: " + member.name)
                if member.isfile():
                    errors.extend(inspect(relative, archive.extractfile(member).read()))
    return [f"{path.name}: {error}" for error in errors]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts", action="store_true", help="Also inspect built wheel and source archives."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        names = source_files(root)
    except ValueError as exc:
        parser.error(str(exc))
    errors = []
    for name in names:
        file = root / name
        if file.is_symlink():
            errors.append("source symlink requires review: " + name)
        elif file.is_file():
            errors.extend(inspect(name, file.read_bytes()))
    archives = []
    if args.artifacts:
        archives = [
            *sorted((root / "dist").glob("*.whl")),
            *sorted((root / "dist").glob("*.tar.gz")),
        ]
        if not any(p.suffix == ".whl" for p in archives) or not any(
            p.name.endswith(".tar.gz") for p in archives
        ):
            errors.append("Build both a wheel and source distribution before the artifact audit.")
        for archive in archives:
            errors.extend(archive_errors(archive))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print(
        f"Public release guard passed: {len(names)} Git candidates, {len(archives)} archives. "
        "No protected files or configured leak patterns found; manual review is still required."
    )


if __name__ == "__main__":
    main()
