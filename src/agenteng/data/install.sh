#!/bin/sh
# Install a checksum-verified AgentEng wheel into a user-owned virtual environment.
set -eu
VERSION=0.0.2
RELEASE_BASE=${AGENTENG_RELEASE_BASE:-https://agentengineering.world/releases/0.0.2}
case "$RELEASE_BASE" in https://*) ;; *) echo 'Release URL must use HTTPS.' >&2; exit 1;; esac
PYTHON=${AGENTENG_PYTHON:-python3}
"$PYTHON" -c 'import sys; sys.version_info >= (3,12) or sys.exit("AgentEng requires Python 3.12+")'
INSTALL_DIR=${AGENTENG_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agenteng}
BIN_DIR=${AGENTENG_BIN_DIR:-$HOME/.local/bin}
if { [ -e "$BIN_DIR/agenteng" ] || [ -L "$BIN_DIR/agenteng" ]; } && [ "$(readlink "$BIN_DIR/agenteng" || true)" != "$INSTALL_DIR/venv/bin/agenteng" ]; then
  echo "Refusing to replace unrelated $BIN_DIR/agenteng" >&2; exit 1
fi
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT HUP INT TERM
WHEEL="agenteng-${VERSION}-py3-none-any.whl"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "$RELEASE_BASE/$WHEEL" -o "$TMP_DIR/$WHEEL"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "$RELEASE_BASE/SHA256SUMS" -o "$TMP_DIR/SHA256SUMS"
"$PYTHON" - "$TMP_DIR" "$WHEEL" <<'PY'
import hashlib, pathlib, sys
root, name = pathlib.Path(sys.argv[1]), sys.argv[2]
rows = [line.split() for line in (root / 'SHA256SUMS').read_text().splitlines()]
expected = [row[0] for row in rows if len(row) == 2 and row[1].lstrip('*') == name]
actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
if len(expected) != 1 or expected[0] != actual:
    raise SystemExit('Release checksum verification failed.')
PY
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
"$PYTHON" -m venv "$INSTALL_DIR/venv"
# CLI + local MCP; RLM remains an optional, separately installed extra.
"$INSTALL_DIR/venv/bin/python" -m pip install "$TMP_DIR/$WHEEL[mcp]"
ln -sf "$INSTALL_DIR/venv/bin/agenteng" "$BIN_DIR/agenteng"
echo "Installed AgentEng $VERSION. Add $BIN_DIR to PATH, then run: agenteng events --upcoming"
