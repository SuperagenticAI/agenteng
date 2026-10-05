#!/bin/sh
#
# AgentEng one-line installer for macOS, Linux, and WSL:
#
#   curl -fsSL https://agentengineering.world/install.sh | sh
#
# Also served at https://a2a.agentengineering.world/install.sh
#
# Installs the latest AgentEng from PyPI (CLI + MCP + A2A extras; RLM stays
# optional and is not included). Bootstraps uv when missing, never uses sudo,
# and falls back to a user virtualenv with pip if uv tool install fails.
#
# Package manager output is captured to a log rather than printed. Set
# AGENTENG_INSTALL_VERBOSE=1 to stream it instead.
#
# Overrides:
#   AGENTENG_VERSION=x.y.z   pin a PyPI version
#   AGENTENG_EXTRAS=server   extras list (default: server = mcp + a2a)
#   AGENTENG_UV_INSTALLER_URL  alternate Astral uv installer URL

set -eu

UV_INSTALLER_URL="${AGENTENG_UV_INSTALLER_URL:-https://astral.sh/uv/install.sh}"
# server extra = mcp + a2a. RLM (pydantic-monty) is parked and excluded.
AGENTENG_EXTRAS_VALUE="${AGENTENG_EXTRAS-server}"
AGENTENG_VERSION_VALUE="${AGENTENG_VERSION:-}"
AGENTENG_VERBOSE="${AGENTENG_INSTALL_VERBOSE:-0}"
A2A_HOST="https://a2a.agentengineering.world"

# ---------------------------------------------------------------------------
# Presentation (Agent Engineering brand: blue -> violet -> magenta)
# ---------------------------------------------------------------------------

ESC=$(printf '\033')
FANCY=0
UTF8=0

case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
    *UTF-8*|*utf-8*|*UTF8*|*utf8*) UTF8=1 ;;
esac

if [ -t 1 ] && [ "$AGENTENG_VERBOSE" = "0" ] && [ -z "${NO_COLOR:-}" ]; then
    case "${TERM:-dumb}" in
        dumb|"") ;;
        *) FANCY=1 ;;
    esac
fi

TRUECOLOR=0
case "${COLORTERM:-}" in
    truecolor|24bit) TRUECOLOR=1 ;;
esac

# Brand hues from docs/assets/logo.png and docs/stylesheets/extra.css:
# blue #357bff, violet #8c1aff (hsl 270 100% 55%), magenta tip #e020b8
# matching the square Agent Engineering lockup. 256-colour fallbacks below.
if [ "$FANCY" = "1" ]; then
    C_RESET="${ESC}[0m"
    C_BOLD="${ESC}[1m"
    C_DIM="${ESC}[2m"
    C_TEXT="${ESC}[38;5;252m"
    C_TRACK="${ESC}[38;5;238m"
    C_GREEN="${ESC}[38;5;42m"
    if [ "$TRUECOLOR" = "1" ]; then
        C_G1="${ESC}[38;2;53;123;255m"
        C_G2="${ESC}[38;2;75;88;239m"
        C_G3="${ESC}[38;2;140;26;255m"
        C_G4="${ESC}[38;2;155;45;205m"
        C_G5="${ESC}[38;2;224;32;184m"
        C_G6="${ESC}[38;2;53;123;255m"
    else
        C_G1="${ESC}[38;5;69m"
        C_G2="${ESC}[38;5;63m"
        C_G3="${ESC}[38;5;93m"
        C_G4="${ESC}[38;5;129m"
        C_G5="${ESC}[38;5;163m"
        C_G6="${ESC}[38;5;69m"
    fi
else
    C_RESET=""
    C_BOLD=""
    C_DIM=""
    C_TEXT=""
    C_TRACK=""
    C_GREEN=""
    C_G1=""
    C_G2=""
    C_G3=""
    C_G4=""
    C_G5=""
    C_G6=""
fi

if [ "$UTF8" = "1" ]; then
    GL_FULL="█"
    GL_MED="▓"
    GL_LOW="░"
    GL_TICK="✓"
    GL_DOT="•"
else
    GL_FULL="#"
    GL_MED="="
    GL_LOW="-"
    GL_TICK="OK"
    GL_DOT="*"
fi

COLUMNS_AVAILABLE="${COLUMNS:-}"
if [ -z "$COLUMNS_AVAILABLE" ] && command -v tput >/dev/null 2>&1; then
    COLUMNS_AVAILABLE=$(tput cols 2>/dev/null || printf '80')
fi
if [ -z "$COLUMNS_AVAILABLE" ]; then
    COLUMNS_AVAILABLE=80
fi
case "$COLUMNS_AVAILABLE" in
    ''|*[!0-9]*) COLUMNS_AVAILABLE=80 ;;
esac

BAR_WIDTH=28
if [ "$COLUMNS_AVAILABLE" -lt 60 ]; then
    BAR_WIDTH=14
fi

LABEL_START="Setting up an isolated environment"
LABEL_FETCH="Downloading components"
LABEL_BUILD="Installing components"
LABEL_LINK="Linking commands"
LABEL_UV="Setting up the installer"
LABEL_PIP="Installing with pip"
if [ "$COLUMNS_AVAILABLE" -lt 72 ]; then
    LABEL_START="Setting up"
    LABEL_FETCH="Downloading"
    LABEL_BUILD="Installing"
    LABEL_LINK="Linking"
fi

TICK=0.1
if ! sleep 0.1 >/dev/null 2>&1; then
    TICK=1
fi

WORK_DIR=""
CURSOR_HIDDEN=0
INSTALL_METHOD=""

cleanup() {
    if [ "$CURSOR_HIDDEN" = "1" ]; then
        printf '%s[?25h' "$ESC"
        CURSOR_HIDDEN=0
    fi
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR"
    fi
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

WORK_DIR=$(mktemp -d 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/agenteng-install.$$")
mkdir -p "$WORK_DIR"
STEP_LOG="${WORK_DIR}/step.log"
STEP_STATUS="${WORK_DIR}/step.status"

say() {
    printf '%s\n' "$1"
}

note() {
    if [ "$FANCY" = "1" ]; then
        printf '  %s%s%s %s%s%s\n' "$C_G3" "$GL_DOT" "$C_RESET" "$C_TEXT" "$1" "$C_RESET"
    else
        printf '%s\n' "$1"
    fi
}

clear_line() {
    printf '\r%s[2K' "$ESC"
}

render_bar() {
    rb_pos=$1
    rb_i=0
    rb_out=""
    while [ "$rb_i" -lt "$BAR_WIDTH" ]; do
        rb_d=$(( rb_pos - rb_i ))
        if [ "$rb_d" -lt 0 ]; then
            rb_d=$(( 0 - rb_d ))
        fi
        if [ "$rb_d" -eq 0 ]; then
            rb_out="${rb_out}${C_G6}${GL_FULL}"
        elif [ "$rb_d" -eq 1 ]; then
            rb_out="${rb_out}${C_G5}${GL_FULL}"
        elif [ "$rb_d" -le 3 ]; then
            rb_out="${rb_out}${C_G4}${GL_FULL}"
        elif [ "$rb_d" -le 5 ]; then
            rb_out="${rb_out}${C_G2}${GL_MED}"
        else
            rb_out="${rb_out}${C_TRACK}${GL_LOW}"
        fi
        rb_i=$(( rb_i + 1 ))
    done
    printf '%s%s' "$rb_out" "$C_RESET"
}

phase_label() {
    pl_default=$1
    if [ ! -s "$STEP_LOG" ]; then
        printf '%s' "$pl_default"
        return
    fi
    if grep -q 'Installed' "$STEP_LOG" 2>/dev/null; then
        printf '%s' "$LABEL_LINK"
    elif grep -q 'Prepared' "$STEP_LOG" 2>/dev/null; then
        printf '%s' "$LABEL_BUILD"
    elif grep -q 'Resolved' "$STEP_LOG" 2>/dev/null; then
        pl_count=$(grep -o 'Resolved [0-9]* package' "$STEP_LOG" 2>/dev/null | head -n 1 | tr -dc '0-9')
        if [ -n "$pl_count" ] && [ "$COLUMNS_AVAILABLE" -ge 72 ]; then
            printf 'Downloading %s components' "$pl_count"
        else
            printf '%s' "$LABEL_FETCH"
        fi
    else
        printf '%s' "$pl_default"
    fi
}

animate() {
    an_label=$1
    an_frame=0
    an_period=$(( (BAR_WIDTH - 1) * 2 ))
    while [ ! -f "$STEP_STATUS" ]; do
        if [ "$FANCY" = "1" ]; then
            an_p=$(( an_frame % an_period ))
            if [ "$an_p" -ge "$BAR_WIDTH" ]; then
                an_pos=$(( an_period - an_p ))
            else
                an_pos=$an_p
            fi
            printf '\r  %s  %s%s%s' \
                "$(render_bar "$an_pos")" "$C_TEXT" "$(phase_label "$an_label")" "$C_RESET"
            printf '%s[K' "$ESC"
        fi
        an_frame=$(( an_frame + 1 ))
        sleep "$TICK"
    done
    if [ "$FANCY" = "1" ]; then
        clear_line
    fi
}

run_step() {
    rs_label=$1
    shift
    rm -f "$STEP_STATUS"
    : > "$STEP_LOG"

    if [ "$AGENTENG_VERBOSE" = "1" ]; then
        say "$rs_label..."
        "$@"
        return $?
    fi

    (
        if "$@" >"$STEP_LOG" 2>&1; then
            printf '0' >"${STEP_STATUS}.tmp"
        else
            printf '%s' "$?" >"${STEP_STATUS}.tmp"
        fi
        mv "${STEP_STATUS}.tmp" "$STEP_STATUS"
    ) &
    rs_pid=$!

    if [ "$FANCY" = "1" ]; then
        printf '%s[?25l' "$ESC"
        CURSOR_HIDDEN=1
    fi
    animate "$rs_label"
    if [ "$FANCY" = "1" ]; then
        printf '%s[?25h' "$ESC"
        CURSOR_HIDDEN=0
    fi

    wait "$rs_pid" 2>/dev/null || true
    rs_rc=$(cat "$STEP_STATUS" 2>/dev/null || printf '1')
    case "$rs_rc" in
        ''|*[!0-9]*) rs_rc=1 ;;
    esac
    return "$rs_rc"
}

step_failed() {
    sf_label=$1
    printf '%s\n' "Error: ${sf_label} failed." >&2
    if [ -s "$STEP_LOG" ]; then
        printf '%s\n' "Output:" >&2
        cat "$STEP_LOG" >&2
    fi
}

banner() {
    if [ "$FANCY" != "1" ]; then
        return
    fi
    printf '\n'
    if [ "$UTF8" = "1" ]; then
        printf '  %s┌%s──%s┐%s  %sAgentEng%s\n' \
            "$C_G1" "$C_G3" "$C_G5" "$C_RESET" "$C_BOLD$C_G3" "$C_RESET"
        printf '  %s│%s%sAE%s%s│%s  %sCLI · MCP · A2A%s\n' \
            "$C_G1" "$C_RESET" "$C_G3" "$C_RESET" "$C_G5" "$C_RESET" \
            "$C_TEXT" "$C_RESET"
        printf '  %s└%s──%s┘%s  %sAgent Engineering HQ%s\n\n' \
            "$C_G1" "$C_G3" "$C_G5" "$C_RESET" "$C_DIM" "$C_RESET"
    else
        printf '  %s%s[ AE ] AgentEng%s\n' "$C_BOLD" "$C_G3" "$C_RESET"
        printf '  %sCLI, MCP and A2A for Agent Engineering HQ.%s\n\n' \
            "$C_TEXT" "$C_RESET"
    fi
}

# Horizontal rule of $1 box-drawing dashes, gradient blue -> violet -> magenta.
logo_hrule() {
    lh_n=$1
    lh_ch="─"
    if [ "$UTF8" != "1" ]; then
        lh_ch="-"
    fi
    lh_i=0
    while [ "$lh_i" -lt "$lh_n" ]; do
        lh_seg=$(( lh_i * 5 / lh_n ))
        case $lh_seg in
            0) lh_c=$C_G1 ;;
            1) lh_c=$C_G2 ;;
            2) lh_c=$C_G3 ;;
            3) lh_c=$C_G4 ;;
            *) lh_c=$C_G5 ;;
        esac
        printf '%s%s' "$lh_c" "$lh_ch"
        lh_i=$(( lh_i + 1 ))
    done
    printf '%s' "$C_RESET"
}

logo_word_agent() {
    printf '%sA%sG%sE%sN%sT%s' \
        "$C_G1" "$C_G2" "$C_G3" "$C_G4" "$C_G5" "$C_RESET"
}

logo_word_engineering() {
    printf '%sE%sN%sG%sI%sN%sE%sE%sR%sI%sN%sG%s' \
        "$C_G1" "$C_G1" "$C_G2" "$C_G2" "$C_G3" "$C_G3" \
        "$C_G4" "$C_G4" "$C_G5" "$C_G5" "$C_G5" "$C_RESET"
}

# One static or animation frame of the square Agent Engineering lockup.
# Always prints exactly 10 lines so cursor-up redraw stays aligned.
# Frame 1: outer box. 2: inner top. 3: inner sides+bottom. 4: AGENT. 5: ENGINEERING.
logo_frame() {
    lf=$1
    if [ "$UTF8" != "1" ]; then
        printf '  +----------------------------+\n'
        printf '  |  +----------------------+  |\n'
        printf '  |  |                      |  |\n'
        printf '  |                            |\n'
        if [ "$lf" -ge 4 ]; then
            printf '  |           AGENT            |\n'
        else
            printf '  |                            |\n'
        fi
        if [ "$lf" -ge 5 ]; then
            printf '  |        ENGINEERING         |\n'
        else
            printf '  |                            |\n'
        fi
        printf '  |                            |\n'
        printf '  |  |                      |  |\n'
        printf '  |  +----------------------+  |\n'
        printf '  +----------------------------+\n'
        return
    fi

    # 1 outer top
    if [ "$lf" -ge 1 ]; then
        printf '  %s┌%s%s┐%s\n' "$C_G1" "$(logo_hrule 28)" "$C_G5" "$C_RESET"
    else
        printf '\n'
    fi

    # 2 inner top
    if [ "$lf" -ge 2 ]; then
        printf '  %s│%s  %s┌%s' "$C_G1" "$C_RESET" "$C_G1" "$C_RESET"
        logo_hrule 22
        printf '%s┐%s  %s│%s\n' "$C_G5" "$C_RESET" "$C_G5" "$C_RESET"
    else
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
    fi

    # 3 inner upper verticals
    if [ "$lf" -ge 3 ]; then
        printf '  %s│%s  %s│%s                      %s│%s  %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G1" "$C_RESET" \
            "$C_G5" "$C_RESET" "$C_G5" "$C_RESET"
    else
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
    fi

    # 4 gap (broken inner verticals, as in the square logo)
    printf '  %s│%s                            %s│%s\n' \
        "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"

    # 5 AGENT (centered in 28 cols: 11 + 5 + 12)
    if [ "$lf" -ge 4 ]; then
        printf '  %s│%s           ' "$C_G1" "$C_RESET"
        logo_word_agent
        printf '            %s│%s\n' "$C_G5" "$C_RESET"
    else
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
    fi

    # 6 ENGINEERING (8 + 11 + 9)
    if [ "$lf" -ge 5 ]; then
        printf '  %s│%s        ' "$C_G1" "$C_RESET"
        logo_word_engineering
        printf '         %s│%s\n' "$C_G5" "$C_RESET"
    else
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
    fi

    # 7 gap
    printf '  %s│%s                            %s│%s\n' \
        "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"

    # 8-9 inner lower verticals + bottom
    if [ "$lf" -ge 3 ]; then
        printf '  %s│%s  %s│%s                      %s│%s  %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G1" "$C_RESET" \
            "$C_G5" "$C_RESET" "$C_G5" "$C_RESET"
        printf '  %s│%s  %s└%s' "$C_G1" "$C_RESET" "$C_G1" "$C_RESET"
        logo_hrule 22
        printf '%s┘%s  %s│%s\n' "$C_G5" "$C_RESET" "$C_G5" "$C_RESET"
    else
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
        printf '  %s│%s                            %s│%s\n' \
            "$C_G1" "$C_RESET" "$C_G5" "$C_RESET"
    fi

    # 10 outer bottom
    if [ "$lf" -ge 1 ]; then
        printf '  %s└%s%s┘%s\n' "$C_G1" "$(logo_hrule 28)" "$C_G5" "$C_RESET"
    else
        printf '\n'
    fi
}

logo() {
    if [ "$FANCY" != "1" ]; then
        return
    fi
    if [ "$COLUMNS_AVAILABLE" -lt 40 ]; then
        printf '\n  %s%sAgentEng%s\n\n' "$C_BOLD" "$C_G3" "$C_RESET"
        return
    fi
    printf '\n'
    # Animate only when fractional sleep works (~0.3s x 5 frames ~= 1.5s).
    # Otherwise print the final lockup in one shot.
    if [ -t 1 ] && [ "$TICK" = "0.1" ]; then
        printf '%s[?25l' "$ESC"
        CURSOR_HIDDEN=1
        lf=1
        while [ "$lf" -le 5 ]; do
            if [ "$lf" -gt 1 ]; then
                printf '%s[10A' "$ESC"
            fi
            logo_frame "$lf"
            lf=$(( lf + 1 ))
            sleep "$TICK"
            sleep "$TICK"
            sleep "$TICK"
        done
        printf '%s[?25h' "$ESC"
        CURSOR_HIDDEN=0
    else
        logo_frame 5
    fi
    printf '\n'
}

# ---------------------------------------------------------------------------
# Discovery and validation
# ---------------------------------------------------------------------------

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
        return
    fi

    if [ -n "${UV_INSTALL_DIR:-}" ] && [ -x "${UV_INSTALL_DIR}/uv" ]; then
        printf '%s\n' "${UV_INSTALL_DIR}/uv"
        return
    fi

    if [ -n "${XDG_BIN_HOME:-}" ] && [ -x "${XDG_BIN_HOME}/uv" ]; then
        printf '%s\n' "${XDG_BIN_HOME}/uv"
        return
    fi

    if [ -n "${HOME:-}" ]; then
        for candidate in "${HOME}/.local/bin/uv" "${HOME}/.cargo/bin/uv"; do
            if [ -x "$candidate" ]; then
                printf '%s\n' "$candidate"
                return
            fi
        done
    fi

    return 1
}

fetch_uv() {
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$UV_INSTALLER_URL" | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$UV_INSTALLER_URL" | sh
    else
        printf '%s\n' "Error: installing uv requires curl or wget." >&2
        exit 1
    fi
}

install_uv() {
    note "AgentEng keeps its tools in an isolated environment, managed by uv."
    note "uv was not found, so the official Astral uv installer will run now."
    note "Installer source: ${UV_INSTALLER_URL}"

    if ! run_step "$LABEL_UV" fetch_uv; then
        step_failed "setting up the installer"
        return 1
    fi
    return 0
}

find_python() {
    if [ -n "${AGENTENG_PYTHON:-}" ]; then
        if command -v "$AGENTENG_PYTHON" >/dev/null 2>&1 || [ -x "$AGENTENG_PYTHON" ]; then
            printf '%s\n' "$AGENTENG_PYTHON"
            return
        fi
    fi
    for candidate in python3.13 python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' \
                >/dev/null 2>&1; then
                printf '%s\n' "$candidate"
                return
            fi
        fi
    done
    return 1
}

build_package_spec() {
    package_spec="agenteng"
    if [ -n "$AGENTENG_EXTRAS_VALUE" ]; then
        package_spec="${package_spec}[${AGENTENG_EXTRAS_VALUE}]"
    fi
    if [ -n "$AGENTENG_VERSION_VALUE" ]; then
        package_spec="${package_spec}==${AGENTENG_VERSION_VALUE}"
    fi
    printf '%s\n' "$package_spec"
}

install_with_pip() {
    python_bin=$(find_python || true)
    if [ -z "$python_bin" ]; then
        printf '%s\n' "Error: Python 3.12+ is required for the pip fallback." >&2
        return 1
    fi

    install_dir="${AGENTENG_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agenteng}"
    bin_dir="${AGENTENG_BIN_DIR:-$HOME/.local/bin}"
    venv_dir="${install_dir}/venv"
    package_spec=$(build_package_spec)

    mkdir -p "$install_dir" "$bin_dir"
    "$python_bin" -m venv "$venv_dir"
    # shellcheck disable=SC2086
    "$venv_dir/bin/python" -m pip install --upgrade pip
    "$venv_dir/bin/python" -m pip install "$package_spec"
    ln -sf "$venv_dir/bin/agenteng" "$bin_dir/agenteng"
    if [ -x "$venv_dir/bin/ae" ]; then
        ln -sf "$venv_dir/bin/ae" "$bin_dir/ae"
    else
        # Older wheels only ship agenteng; expose the ae alias anyway.
        ln -sf "$venv_dir/bin/agenteng" "$bin_dir/ae"
    fi
    printf '%s\n' "$bin_dir" >"${WORK_DIR}/pip_bin_dir"
    printf '%s\n' "$bin_dir/agenteng" >"${WORK_DIR}/agenteng_bin"
}

validate_options() {
    case "$AGENTENG_EXTRAS_VALUE" in
        *[!A-Za-z0-9,_-]*)
            printf '%s\n' \
                "Error: AGENTENG_EXTRAS may contain only letters, numbers, commas, '_' and '-'." \
                >&2
            exit 1
            ;;
    esac
    case "$AGENTENG_VERSION_VALUE" in
        *[!A-Za-z0-9._+!-]*)
            printf '%s\n' "Error: AGENTENG_VERSION contains unsupported characters." >&2
            exit 1
            ;;
    esac
}

validate_options

banner

package_spec=$(build_package_spec)

install_message="Installing AgentEng from PyPI"
if [ -n "$AGENTENG_VERSION_VALUE" ]; then
    install_message="${install_message} (${AGENTENG_VERSION_VALUE})"
else
    install_message="${install_message} (latest)"
fi
if [ -n "$AGENTENG_EXTRAS_VALUE" ]; then
    install_message="${install_message} with extras: ${AGENTENG_EXTRAS_VALUE}"
fi
note "$install_message"

uv_bin="$(find_uv || true)"
if [ -z "$uv_bin" ]; then
    if install_uv; then
        uv_bin="$(find_uv || true)"
    else
        note "uv setup failed; falling back to a user virtualenv with pip."
    fi
fi

agenteng_bin=""
tool_bin=""

if [ -n "$uv_bin" ]; then
    if run_step "$LABEL_START" \
        "$uv_bin" tool install \
            --no-config \
            --upgrade \
            --force \
            --python 3.12 \
            "$package_spec"; then
        INSTALL_METHOD="uv"
        # uv may colour paths when stdout is a TTY; force plain text.
        tool_bin="$(NO_COLOR=1 "$uv_bin" tool dir --bin --no-config)"
        tool_bin=$(printf '%s' "$tool_bin" | tr -d '\r')
        agenteng_bin="${tool_bin}/agenteng"
    else
        note "uv tool install failed; falling back to a user virtualenv with pip."
        if [ -s "$STEP_LOG" ] && [ "$AGENTENG_VERBOSE" = "1" ]; then
            cat "$STEP_LOG"
        fi
    fi
fi

if [ -z "$agenteng_bin" ]; then
    if ! run_step "$LABEL_PIP" install_with_pip; then
        step_failed "installing AgentEng"
        exit 1
    fi
    INSTALL_METHOD="pip"
    tool_bin=$(cat "${WORK_DIR}/pip_bin_dir")
    agenteng_bin=$(cat "${WORK_DIR}/agenteng_bin")
fi

if [ ! -x "$agenteng_bin" ]; then
    printf '%s\n' \
        "Error: AgentEng was installed but ${agenteng_bin} was not found." \
        >&2
    exit 1
fi

# Prefer the package ae entry point; otherwise symlink ae -> agenteng so the
# short command is always on PATH after this installer runs.
ae_bin="${tool_bin}/ae"
if [ ! -x "$ae_bin" ]; then
    ln -sf "$agenteng_bin" "$ae_bin"
fi

agenteng_version="$("$agenteng_bin" --version)"

logo

if [ "$FANCY" = "1" ]; then
    printf '  %s%s%s %s%s%s\n\n' \
        "$C_GREEN" "$GL_TICK" "$C_RESET" "$C_TEXT" "$agenteng_version" "$C_RESET"
    printf '  %s%sAgentEng is installed.%s\n' "$C_BOLD" "$C_G3" "$C_RESET"
    printf '  %sBuilt for coding agents exploring Agent Engineering HQ.%s\n\n' \
        "$C_DIM" "$C_RESET"
    printf '  %sNext steps for agents%s\n' "$C_BOLD" "$C_RESET"
    printf '  %s%s%s ae discover\n' "$C_G1" "$GL_DOT" "$C_RESET"
    printf '  %s%s%s ae events --upcoming\n' "$C_G2" "$GL_DOT" "$C_RESET"
    printf '  %s%s%s ae connect cursor\n' "$C_G3" "$GL_DOT" "$C_RESET"
    printf '  %s%s%s ae connect claude-code\n' "$C_G4" "$GL_DOT" "$C_RESET"
    printf '  %s%s%s ae connect codex\n\n' "$C_G5" "$GL_DOT" "$C_RESET"
    printf '  %sHosted MCP / A2A%s\n' "$C_BOLD" "$C_RESET"
    printf '  %s%s%s %s\n' "$C_G1" "$GL_DOT" "$C_RESET" "$A2A_HOST"
    printf '  %s%s%s %s/.well-known/agent-card.json\n' "$C_G3" "$GL_DOT" "$C_RESET" "$A2A_HOST"
    printf '  %s%s%s %s/mcp/\n\n' "$C_G5" "$GL_DOT" "$C_RESET" "$A2A_HOST"
    printf '  %sUpgrade later by running this installer again.%s\n' "$C_DIM" "$C_RESET"
    if [ "$INSTALL_METHOD" = "uv" ]; then
        printf '  %sUninstall with: %s tool uninstall agenteng%s\n\n' \
            "$C_DIM" "$uv_bin" "$C_RESET"
    else
        printf '  %sUninstall by removing %s and the agenteng/ae symlinks.%s\n\n' \
            "$C_DIM" "${AGENTENG_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/agenteng}" "$C_RESET"
    fi
else
    say "$agenteng_version"
    say "AgentEng is installed."
    say "Next steps for agents:"
    say "  ae discover"
    say "  ae events --upcoming"
    say "  ae connect cursor"
    say "  ae connect claude-code"
    say "  ae connect codex"
    say "Hosted MCP / A2A: ${A2A_HOST}"
    say "Agent card: ${A2A_HOST}/.well-known/agent-card.json"
    say "MCP: ${A2A_HOST}/mcp/"
    say "Upgrade later by running this installer again."
    if [ "$INSTALL_METHOD" = "uv" ]; then
        say "Uninstall with: ${uv_bin} tool uninstall agenteng"
    else
        say "Uninstall by removing the AgentEng venv and the agenteng/ae symlinks."
    fi
fi

case ":${PATH}:" in
    *":${tool_bin}:"*) ;;
    *)
        if [ "$FANCY" = "1" ]; then
            printf '  %sRestart your shell if '"'"'ae'"'"' is not found; %s must be on PATH.%s\n\n' \
                "$C_G6" "$tool_bin" "$C_RESET"
        else
            printf '%s\n' \
                "Restart your shell if 'ae' is not found; ${tool_bin} must be on PATH."
        fi
        ;;
esac
