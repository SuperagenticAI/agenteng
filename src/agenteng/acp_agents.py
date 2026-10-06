"""Known ACP coding agents and how to launch them (no ACP SDK needed).

Launch commands follow the official ACP registry
(https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json) and each
agent's own ACP documentation. ``agenteng code --list`` only checks ``PATH``; it never
installs or runs an agent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import shlex
import shutil

REGISTRY_URL = "https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    title: str
    command: tuple[str, ...]
    install: str
    source: str
    npm_package: str | None = None
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def binary(self) -> str:
        return self.command[0]

    def resolve(self) -> str | None:
        """Absolute path of the agent binary on PATH, or None."""
        return shutil.which(self.binary)

    def argv(self, *, npx: bool = False) -> list[str]:
        """Command line to spawn this agent over stdio."""
        path = self.resolve()
        if path:
            return [path, *self.command[1:]]
        if npx and self.npm_package:
            runner = shutil.which("npx")
            if runner:
                return [runner, "-y", self.npm_package, *self.command[1:]]
        raise LookupError(self.missing_message())

    def missing_message(self) -> str:
        hint = f" Install it with: {self.install}" if self.install else ""
        npx = (
            " Or rerun with --npx to launch it through npx."
            if self.npm_package and shutil.which("npx")
            else ""
        )
        return f"{self.title} ({self.binary}) is not on PATH.{hint}{npx}"

    def as_dict(self) -> dict:
        data = asdict(self)
        data["command"] = shlex.join(self.command)
        data["aliases"] = list(self.aliases)
        data["path"] = self.resolve()
        data["installed"] = data["path"] is not None
        return data


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        name="claude",
        title="Claude Code (ACP adapter)",
        command=("claude-agent-acp",),
        npm_package="@agentclientprotocol/claude-agent-acp",
        install="npm install -g @agentclientprotocol/claude-agent-acp",
        source="https://github.com/agentclientprotocol/claude-agent-acp",
        notes="Uses your existing Claude Code login or ANTHROPIC_API_KEY.",
        aliases=("claude-code", "claude-acp"),
    ),
    AgentSpec(
        name="codex",
        title="Codex (ACP adapter)",
        command=("codex-acp",),
        npm_package="@agentclientprotocol/codex-acp",
        install="npm install -g @agentclientprotocol/codex-acp",
        source="https://github.com/agentclientprotocol/codex-acp",
        notes="Uses your existing Codex login or OPENAI_API_KEY.",
        aliases=("codex-acp",),
    ),
    AgentSpec(
        name="gemini",
        title="Gemini CLI",
        command=("gemini", "--acp"),
        npm_package="@google/gemini-cli",
        install="npm install -g @google/gemini-cli",
        source="https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/acp-mode.md",
        notes="Native ACP mode. Sign in with `gemini` first.",
        aliases=("gemini-cli",),
    ),
    AgentSpec(
        name="copilot",
        title="GitHub Copilot CLI",
        command=("copilot", "--acp"),
        npm_package="@github/copilot",
        install="npm install -g @github/copilot",
        source="https://github.blog/changelog/2026-01-28-acp-support-in-copilot-cli-is-now-in-public-preview/",
        notes="Native ACP mode (public preview). Sign in with `copilot` first.",
        aliases=("github-copilot", "github-copilot-cli"),
    ),
    AgentSpec(
        name="cursor",
        title="Cursor Agent CLI",
        command=("cursor-agent", "acp"),
        install="curl https://cursor.com/install -fsS | bash",
        source="https://cursor.com/docs/cli/acp",
        notes="Native ACP mode. Sign in with `cursor-agent login` first.",
        aliases=("cursor-agent",),
    ),
    AgentSpec(
        name="opencode",
        title="OpenCode",
        command=("opencode", "acp"),
        npm_package="opencode-ai",
        install="npm install -g opencode-ai",
        source="https://opencode.ai/docs/acp/",
        notes="Native ACP mode.",
    ),
    AgentSpec(
        name="goose",
        title="goose",
        command=("goose", "acp"),
        install="See https://github.com/aaif-goose/goose#install",
        source="https://github.com/aaif-goose/goose",
        notes="Native ACP mode. Configure a provider with `goose configure` first.",
    ),
    AgentSpec(
        name="qwen",
        title="Qwen Code",
        command=("qwen", "--acp"),
        npm_package="@qwen-code/qwen-code",
        install="npm install -g @qwen-code/qwen-code",
        source="https://github.com/QwenLM/qwen-code",
        notes="Native ACP mode.",
        aliases=("qwen-code",),
    ),
    AgentSpec(
        name="fast-agent",
        title="fast-agent",
        command=("fast-agent-acp",),
        install="uv tool install fast-agent-acp",
        source="https://github.com/evalstate/fast-agent",
        notes="Python ACP agent. `--agent-command 'fast-agent-acp --model passthrough'` runs "
        "offline with no model or credentials (echo and ***CALL_TOOL only).",
        aliases=("fast-agent-acp",),
    ),
    AgentSpec(
        name="kimi",
        title="Kimi CLI",
        command=("kimi", "acp"),
        install="See https://github.com/MoonshotAI/kimi-cli",
        source="https://github.com/MoonshotAI/kimi-cli",
        notes="Native ACP mode.",
        aliases=("kimi-cli",),
    ),
)


def find_agent(name: str) -> AgentSpec:
    wanted = name.strip().lower()
    for spec in AGENTS:
        if wanted == spec.name or wanted in spec.aliases:
            return spec
    known = ", ".join(spec.name for spec in AGENTS)
    raise LookupError(f"Unknown agent {name!r}. Known agents: {known}. Or use --agent-command.")


def installed_agents() -> list[AgentSpec]:
    return [spec for spec in AGENTS if spec.resolve()]


def default_agent() -> AgentSpec:
    """First installed agent in catalogue order."""
    found = installed_agents()
    if not found:
        raise LookupError(
            "No ACP coding agent found on PATH. Run `agenteng code --list` for install commands, "
            "or pass --agent-command."
        )
    return found[0]
