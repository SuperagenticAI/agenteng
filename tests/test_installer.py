import os
from pathlib import Path
import subprocess

import pytest

INSTALLER = Path(__file__).resolve().parents[1] / "src/agenteng/data/install.sh"

pytestmark = pytest.mark.skipif(not Path("/bin/sh").exists(), reason="POSIX sh is required")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _fake_uv_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    command_bin = tmp_path / "commands"
    tool_bin = tmp_path / "tools"
    command_bin.mkdir()
    tool_bin.mkdir()
    uv_log = tmp_path / "uv.log"

    _write_executable(
        command_bin / "uv",
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
if [ "$1" = "tool" ] && [ "$2" = "install" ]; then
    exit 0
fi
if [ "$1" = "tool" ] && [ "$2" = "dir" ]; then
    printf '%s\\n' "$FAKE_TOOL_BIN"
    exit 0
fi
exit 2
""",
    )
    _write_executable(
        tool_bin / "agenteng",
        "#!/bin/sh\nprintf '%s\\n' 'agenteng, version 0.test'\n",
    )

    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PATH": os.pathsep.join((str(command_bin), os.environ.get("PATH", ""))),
        "FAKE_UV_LOG": str(uv_log),
        "FAKE_TOOL_BIN": str(tool_bin),
        "NO_COLOR": "1",
        "TERM": "dumb",
    }
    return env, uv_log, tool_bin


def test_installer_is_valid_posix_shell():
    result = subprocess.run(
        ["sh", "-n", str(INSTALLER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    text = INSTALLER.read_text(encoding="utf-8")
    assert "uv tool install" in text
    assert "agenteng" in text
    assert "SuperQode" not in text and "superqode" not in text
    assert "agentengineering.world/releases/" not in text
    assert "AGENTENG_EXTRAS" in text
    assert "AGENTENG_VERSION" in text
    assert "ae discover" in text
    assert 'ln -sf "$agenteng_bin" "$ae_bin"' in text or "ae_bin=" in text


def test_installer_uses_uv_tool_install_latest_with_server_extras(tmp_path: Path):
    env, uv_log, tool_bin = _fake_uv_environment(tmp_path)

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "agenteng, version 0.test" in result.stdout
    assert "AgentEng is installed" in result.stdout
    assert "ae discover" in result.stdout
    assert "ae events --upcoming" in result.stdout
    assert "a2a.agentengineering.world" in result.stdout
    assert (tool_bin / "ae").is_symlink() or (tool_bin / "ae").is_file()
    uv_calls = uv_log.read_text(encoding="utf-8")
    assert ("tool install --no-config --upgrade --force --python 3.12 agenteng[server]") in uv_calls
    assert "tool dir --bin --no-config" in uv_calls


def test_installer_supports_explicit_extras_and_version_pin(tmp_path: Path):
    env, uv_log, _tool_bin = _fake_uv_environment(tmp_path)
    env["AGENTENG_EXTRAS"] = "mcp"
    env["AGENTENG_VERSION"] = "0.0.3"

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (
        "tool install --no-config --upgrade --force --python 3.12 agenteng[mcp]==0.0.3"
    ) in uv_log.read_text(encoding="utf-8")


def test_installer_rejects_malformed_options_before_running_uv(tmp_path: Path):
    env, uv_log, _tool_bin = _fake_uv_environment(tmp_path)
    env["AGENTENG_EXTRAS"] = "mcp;unexpected"

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "AGENTENG_EXTRAS may contain only" in result.stderr
    assert not uv_log.exists()


def test_installer_rejects_malformed_version(tmp_path: Path):
    env, uv_log, _tool_bin = _fake_uv_environment(tmp_path)
    env["AGENTENG_VERSION"] = "0.0.3;rm"

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "AGENTENG_VERSION contains unsupported characters" in result.stderr
    assert not uv_log.exists()


def test_installer_bootstraps_uv_when_it_is_missing(tmp_path: Path):
    command_bin = tmp_path / "commands"
    tool_bin = tmp_path / "tools"
    home_dir = tmp_path / "home"
    command_bin.mkdir()
    tool_bin.mkdir()
    uv_log = tmp_path / "uv.log"
    uv_template = tmp_path / "uv-template"
    bootstrap = tmp_path / "uv-bootstrap.sh"

    _write_executable(
        uv_template,
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
if [ "$1" = "tool" ] && [ "$2" = "install" ]; then exit 0; fi
if [ "$1" = "tool" ] && [ "$2" = "dir" ]; then
    printf '%s\\n' "$FAKE_TOOL_BIN"
    exit 0
fi
exit 2
""",
    )
    bootstrap.write_text(
        """#!/bin/sh
mkdir -p "$HOME/.local/bin"
cp "$FAKE_UV_TEMPLATE" "$HOME/.local/bin/uv"
chmod +x "$HOME/.local/bin/uv"
""",
        encoding="utf-8",
    )
    _write_executable(
        command_bin / "curl",
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FAKE_CURL_LOG"\ncat "$FAKE_BOOTSTRAP"\n',
    )
    _write_executable(
        tool_bin / "agenteng",
        "#!/bin/sh\nprintf '%s\\n' 'agenteng, version 0.test'\n",
    )
    curl_log = tmp_path / "curl.log"
    env = {
        **os.environ,
        "HOME": str(home_dir),
        "PATH": os.pathsep.join((str(command_bin), "/usr/bin", "/bin")),
        "FAKE_BOOTSTRAP": str(bootstrap),
        "FAKE_CURL_LOG": str(curl_log),
        "FAKE_TOOL_BIN": str(tool_bin),
        "FAKE_UV_LOG": str(uv_log),
        "FAKE_UV_TEMPLATE": str(uv_template),
        "AGENTENG_UV_INSTALLER_URL": "https://example.test/uv-install.sh",
        "NO_COLOR": "1",
        "TERM": "dumb",
    }

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "official Astral uv installer will run now" in result.stdout
    assert "-LsSf https://example.test/uv-install.sh" in curl_log.read_text(encoding="utf-8")
    assert (home_dir / ".local/bin/uv").is_file()


def test_installer_falls_back_to_pip_when_uv_tool_install_fails(tmp_path: Path):
    command_bin = tmp_path / "commands"
    home_dir = tmp_path / "home"
    command_bin.mkdir()
    home_dir.mkdir()
    uv_log = tmp_path / "uv.log"
    pip_log = tmp_path / "pip.log"

    _write_executable(
        command_bin / "uv",
        """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_UV_LOG"
if [ "$1" = "tool" ] && [ "$2" = "install" ]; then
    echo "simulated uv failure" >&2
    exit 1
fi
if [ "$1" = "tool" ] && [ "$2" = "dir" ]; then
    printf '%s\\n' "$HOME/.local/bin"
    exit 0
fi
exit 2
""",
    )
    # Fake python that creates a minimal venv layout when asked.
    _write_executable(
        command_bin / "python3",
        """#!/bin/sh
if [ "$1" = "-c" ]; then
    exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
    venv=$3
    mkdir -p "$venv/bin"
    cat > "$venv/bin/python" <<'PY'
#!/bin/sh
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
    printf '%s\\n' "$*" >> "$FAKE_PIP_LOG"
    exit 0
fi
exit 0
PY
    chmod +x "$venv/bin/python"
    cat > "$venv/bin/agenteng" <<'AE'
#!/bin/sh
printf '%s\\n' 'agenteng, version 0.pip'
AE
    chmod +x "$venv/bin/agenteng"
    exit 0
fi
exit 0
""",
    )

    env = {
        **os.environ,
        "HOME": str(home_dir),
        "PATH": os.pathsep.join((str(command_bin), "/usr/bin", "/bin")),
        "FAKE_UV_LOG": str(uv_log),
        "FAKE_PIP_LOG": str(pip_log),
        "AGENTENG_PYTHON": str(command_bin / "python3"),
        "AGENTENG_INSTALL_DIR": str(home_dir / "share" / "agenteng"),
        "AGENTENG_BIN_DIR": str(home_dir / "bin"),
        "NO_COLOR": "1",
        "TERM": "dumb",
    }

    result = subprocess.run(
        ["sh", str(INSTALLER)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "falling back to a user virtualenv with pip" in result.stdout
    assert "agenteng, version 0.pip" in result.stdout
    assert (home_dir / "bin" / "agenteng").is_symlink()
    assert (home_dir / "bin" / "ae").is_symlink()
