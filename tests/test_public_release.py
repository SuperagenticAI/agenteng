import importlib.util
from pathlib import Path
import subprocess
import tarfile
import zipfile
import io

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "public_release", ROOT / "scripts/check-public-release.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.mark.parametrize(
    "name",
    [
        ".private/notes.md",
        "PLAN.md",
        "docs/IMPLEMENTATION.md",
        ".env.production",
        "operator.pem",
        "service-account-test.json",
        "submissions/proposal.json",
        "proposal-drafts/talk.json",
        "attendees.csv",
        "contacts-export.csv",
        "draft.json",
        "talk.md",
        "proposal-speaker.json",
        "../outside.txt",
        "/etc/passwd",
    ],
)
def test_protected_release_paths(name):
    assert guard.protected(name)


@pytest.mark.parametrize(
    "name",
    [
        ".env.example",
        "LICENSE",
        ".editorconfig",
        ".gitattributes",
        "src/agenteng/data/tools.json",
        "src/agenteng/data/install.sh",
        "docs/COMMUNITY.md",
        "tests/test_public_release.py",
        ".github/ISSUE_TEMPLATE/event_idea.yml",
    ],
)
def test_expected_public_release_paths(name):
    assert not guard.protected(name)


def test_secret_detection_reports_location_without_value():
    credential = "ghp_" + "x" * 36
    errors = guard.inspect("example.txt", ("\n" + credential).encode())
    assert errors == ["example.txt:2: GitHub credential"]
    assert credential not in str(errors)
    local = "/" + "Users" + "/sample/private/"
    assert "local home path" in guard.inspect("example.txt", local.encode())[0]


def test_archive_guard_catches_notes_and_credentials(tmp_path):
    wheel = tmp_path / "example.whl"
    credential = "sk-" + "x" * 40
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("package/.private/notes.md", "Internal notes")
        archive.writestr("package/leak.txt", credential)
    errors = guard.archive_errors(wheel)
    assert any("private file" in error for error in errors)
    assert any("model credential" in error for error in errors)
    assert credential not in str(errors)
    source = tmp_path / "example.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        member = tarfile.TarInfo("package/PLAN.md")
        member.size = 5
        archive.addfile(member, io.BytesIO(b"notes"))
    assert "private file" in guard.archive_errors(source)[0]


def test_gitignore_protects_local_files_but_keeps_installer_public():
    # Source archives have no Git checkout; artifact checks cover those separately.
    if not (ROOT / ".git").is_dir():
        pytest.skip("Git-checkout-only ignore validation")
    names = [
        ".private/notes.md",
        "PLAN.md",
        ".env.local",
        ".venv/bin/python",
        "dist/install.sh",
        "proposal-drafts/talk.json",
        "submissions/contact.json",
        "draft.json",
        "talk.md",
        "proposal-speaker.json",
        "contacts-export.csv",
    ]
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=ROOT,
        input="\n".join(names) + "\n",
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == names
    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=ROOT,
        input=".env.example\nsrc/agenteng/data/install.sh\n",
        capture_output=True,
        text=True,
    )
    assert not result.stdout
