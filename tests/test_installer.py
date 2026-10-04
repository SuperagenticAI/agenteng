import os
from pathlib import Path
import subprocess
import sys

INSTALLER = Path(__file__).resolve().parents[1] / "src/agenteng/data/install.sh"


def test_installer_rejects_non_https_before_install(tmp_path):
    result = subprocess.run(
        ["/bin/sh", str(INSTALLER)],
        env={
            **os.environ,
            "AGENTENG_RELEASE_BASE": "http://example.com",
            "AGENTENG_INSTALL_DIR": str(tmp_path / "install"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "HTTPS" in result.stderr
    assert not (tmp_path / "install").exists()


def test_installer_rejects_corrupt_artifact_before_install(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    fixture = tmp_path / "release"
    fixture.mkdir()
    wheel = "agenteng-0.1.0-py3-none-any.whl"
    (fixture / wheel).write_bytes(b"corrupt artifact")
    (fixture / "SHA256SUMS").write_text("0" * 64 + "  " + wheel + "\n")
    fake = tools / "curl"
    fake.write_text("""#!/bin/sh
while [ "$#" -gt 0 ]; do
  case "$1" in https://*) URL=$1;; -o) shift; DEST=$1;; esac
  shift
done
cp "$AGENTENG_TEST_RELEASE/$(basename "$URL")" "$DEST"
""")
    fake.chmod(0o755)
    install = tmp_path / "install"
    result = subprocess.run(
        ["/bin/sh", str(INSTALLER)],
        env={
            **os.environ,
            "PATH": str(tools) + os.pathsep + os.environ["PATH"],
            "AGENTENG_PYTHON": sys.executable,
            "AGENTENG_RELEASE_BASE": "https://release.example",
            "AGENTENG_INSTALL_DIR": str(install),
            "AGENTENG_BIN_DIR": str(tmp_path / "bin"),
            "AGENTENG_TEST_RELEASE": str(fixture),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "checksum verification failed" in result.stderr
    assert not install.exists()


def test_installer_preserves_unrelated_executable(tmp_path):
    binary = tmp_path / "agenteng"
    binary.write_text("existing executable")
    result = subprocess.run(
        ["/bin/sh", str(INSTALLER)],
        env={
            **os.environ,
            "AGENTENG_PYTHON": sys.executable,
            "AGENTENG_BIN_DIR": str(tmp_path),
            "AGENTENG_INSTALL_DIR": str(tmp_path / "install"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "unrelated" in result.stderr
    assert binary.read_text() == "existing executable"
    assert not (tmp_path / "install").exists()


def test_installer_preserves_unrelated_broken_symlink(tmp_path):
    binary = tmp_path / "agenteng"
    target = tmp_path / "unrelated-missing-program"
    binary.symlink_to(target)
    result = subprocess.run(
        ["/bin/sh", str(INSTALLER)],
        env={
            **os.environ,
            "AGENTENG_PYTHON": sys.executable,
            "AGENTENG_BIN_DIR": str(tmp_path),
            "AGENTENG_INSTALL_DIR": str(tmp_path / "install"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "unrelated" in result.stderr
    assert binary.is_symlink() and binary.readlink() == target
    assert not (tmp_path / "install").exists()
