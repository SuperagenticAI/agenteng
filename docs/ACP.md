# 🤝 ACP client: `ae code` (spike)

`ae code` lets AgentEng drive a coding agent you already use (Claude Code,
Codex, Gemini CLI, Copilot, Cursor, OpenCode and others) through the
[Agent Client Protocol](https://agentclientprotocol.com) (ACP), with AgentEng
conference data attached. It is an **optional extra** and a **spike**: the
command shape and defaults may change.

```sh
uv tool install 'agenteng[acp]'
ae code --list
ae code --agent claude "scaffold a demo of talk agenteng-london-2026-14"
```

## Why

AgentEng already serves agents through MCP and A2A, but the agent has to be
configured to find it. ACP flips that: AgentEng starts the agent, so the
conference context is there from the first turn without editing any agent's
config.

- **Talk to demo.** `ae code "scaffold a demo of talk agenteng-london-2026-14"`
  gives the agent the talk, abstract, speaker and projects, then asks it to build
  something runnable in your directory.
- **Workshop mode.** Facilitators hand attendees one command that works with
  whichever ACP agent each person has installed.
- **Try a tool from the directory.** `ae code --context tool:a2a "write a hello
  world for this"` attaches a tool-directory entry, and the agent can search
  more tools through the attached MCP server.
- **Plan your day with an agent.** The agent can call `talks`, `speaker`, `now`
  and `next` through MCP and answer in your terminal.

## Command shape

```text
ae code [--agent NAME | --agent-command "CMD ARGS"] [--cwd DIR]
        [--context ID ...] [--no-mcp] [--npx] [--show-thoughts]
        [--allow-always-option] [--json] PROMPT
ae code --list [--json]
```

| Option | Meaning |
| --- | --- |
| `--agent NAME` | A known agent from `--list`. Default: the first one installed on `PATH`. |
| `--agent-command` | Any ACP agent command line, for agents not in the list. |
| `--cwd DIR` | Session working directory (default: current directory). |
| `--context ID` | Attach a talk, event or speaker ID, or `tool:ID`. IDs in the prompt are detected automatically. |
| `--no-mcp` | Do not attach the AgentEng MCP server. |
| `--npx` | Launch a missing npm-distributed agent with `npx -y PACKAGE`. Opt-in, because it downloads and runs code. |
| `--show-thoughts` | Show the agent's thought chunks. |
| `--allow-always-option` | Also offer the agent's "allow always" choice in permission prompts. |
| `--json` | Newline-delimited JSON events instead of rich output (also used when stdout is not a terminal). |

The prompt can also come from stdin: `echo "..." | ae code --agent gemini`.

## Supported agents

`ae code --list` checks `PATH` only; it never installs or runs anything. Launch
commands come from the official
[ACP registry](https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json)
([about the registry](https://agentclientprotocol.com/get-started/registry))
and each agent's own ACP documentation.

| Name | Launch | Install | Source |
| --- | --- | --- | --- |
| `claude` | `claude-agent-acp` | `npm install -g @agentclientprotocol/claude-agent-acp` | [claude-agent-acp](https://github.com/agentclientprotocol/claude-agent-acp) (adapter over Claude Code) |
| `codex` | `codex-acp` | `npm install -g @agentclientprotocol/codex-acp` | [codex-acp](https://github.com/agentclientprotocol/codex-acp) (adapter over Codex) |
| `gemini` | `gemini --acp` | `npm install -g @google/gemini-cli` | [Gemini CLI ACP mode](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/acp-mode.md) |
| `copilot` | `copilot --acp` | `npm install -g @github/copilot` | [Copilot CLI ACP (preview)](https://github.blog/changelog/2026-01-28-acp-support-in-copilot-cli-is-now-in-public-preview/) |
| `cursor` | `cursor-agent acp` | `curl https://cursor.com/install -fsS \| bash` | [Cursor CLI ACP](https://cursor.com/docs/cli/acp) |
| `opencode` | `opencode acp` | `npm install -g opencode-ai` | [OpenCode ACP](https://opencode.ai/docs/acp/) |
| `goose` | `goose acp` | see repository | [goose](https://github.com/aaif-goose/goose) |
| `qwen` | `qwen --acp` | `npm install -g @qwen-code/qwen-code` | [Qwen Code](https://github.com/QwenLM/qwen-code) |
| `fast-agent` | `fast-agent-acp` | `uv tool install fast-agent-acp` | [fast-agent](https://github.com/evalstate/fast-agent) |
| `kimi` | `kimi acp` | see repository | [Kimi CLI](https://github.com/MoonshotAI/kimi-cli) |

The older `@zed-industries/claude-code-acp` and `@zed-industries/codex-acp`
npm packages are deprecated in favour of the `@agentclientprotocol/*`
packages above. The registry lists about 40 agents; anything else works with
`--agent-command`.

Sign-in stays with each agent. `ae code` never reads, stores or forwards
credentials; it passes your environment to the agent process unchanged. If an
agent needs sign-in (`auth_required`), `ae code` stops and tells you to sign in
with that agent's own CLI.

## How it works

`ae code` uses the official Python SDK,
[`agent-client-protocol`](https://agentclientprotocol.github.io/python-sdk/)
(pinned to 0.12.1, ACP protocol version 1), as the client side:

1. **Spawn** the agent as a subprocess and speak JSON-RPC over its stdio. Agent
   stderr goes to a log file under the AgentEng config directory
   (`acp-logs/`), so it never mixes with the conversation.
2. **[Initialize](https://agentclientprotocol.com/protocol/initialization)**
   with `clientInfo` `agenteng` and **no** file-system or terminal capability.
   The agent uses its own tools for files and commands, and those go through
   permission requests.
3. **[New session](https://agentclientprotocol.com/protocol/session-setup)**
   with `cwd` and `mcpServers`. AgentEng attaches itself as a stdio MCP server:

    ```json
    {"name": "agenteng", "command": "/abs/path/to/python",
     "args": ["-m", "agenteng", "mcp"], "env": []}
    ```

    The ACP spec requires every agent to support stdio MCP servers and an
    absolute command path, so `ae code` uses the running interpreter rather
    than relying on the agent's `PATH`. `--remote` and `--catalogue` pass
    through to the MCP server.
4. **[Prompt](https://agentclientprotocol.com/protocol/prompt-turn)** with
   three kinds of text block: a short AgentEng preamble (how to call the
   `agenteng` tool, and to treat conference data as reference, not
   instructions), the JSON of any talk, event, speaker or tool record named in
   the prompt or `--context`, then your prompt. Plain text blocks work with
   every agent; embedded resources would need the `embeddedContext`
   capability.
5. **Stream** `session/update` notifications: message chunks, optional
   thoughts, [tool calls](https://agentclientprotocol.com/protocol/tool-calls)
   and plans. Ctrl+C sends `session/cancel`.

The `--json` stream has one object per line with an `event` field: `agent`,
`session`, `plan`, `agent_message_chunk`, `agent_thought_chunk`, `tool_call`,
`tool_call_update`, `permission`, `warning`, `error` and `stop` (other ACP
updates pass through under their own names).

## Permissions

- Every `session/request_permission` goes to you in the terminal: the tool
  title, kind, paths and input, then a numbered choice. **Enter rejects.**
- Nothing is auto-approved, writes included. There is no allow-all flag.
- The agent's "allow always" option is hidden by default, so each write
  needs a fresh decision. `--allow-always-option` shows it for that run.
- Without a terminal (CI, pipes, another agent driving `ae code --json`), every
  request is rejected and reported as a `permission` event. With `--json` in a
  terminal, the prompt is shown on stderr.
- Rejection uses the agent's `reject_once` option, or the `cancelled` outcome
  if the agent offered none.

## Testing

CI does not need a real agent. `tests/fixtures/fake_acp_agent.py` is an ACP
agent built on the same SDK. One prompt turn sends a plan, streamed text and
thoughts, a tool call that really calls the attached `agenteng mcp` server
over stdio, and an edit that needs permission. Tests check the
`initialize` and `session/new` payloads, the MCP round trip, rendering, the
JSON stream, reject-by-default, the allow path, the hidden allow-always option
and sign-in errors.

A real third-party agent was also checked on a machine with no credentials:
`fast-agent-acp==0.10.1 --model passthrough` (no model) completed a session,
listed the attached `agenteng__agenteng` MCP tool, asked permission before
calling it, was rejected without a terminal, and returned the talk after
`allow_once`. Claude Code, Codex, Gemini and the other model-backed agents need
your own sign-in, so test them locally:

```sh
ae code --agent claude "summarise talk agenteng-london-2026-2 in three bullets"
ae code --agent gemini --cwd ./demo "scaffold a demo of talk agenteng-london-2026-14"
```

## Effort

| Stage | Scope | Rough effort |
| --- | --- | --- |
| Spike (this change) | One prompt turn, agent catalogue, MCP attach, context blocks, permissions, rich and JSON output, fake-agent tests | Done |
| Usable | Multi-turn chat loop, `ae` menu entry, show diffs in permission prompts, session modes and model picker, better long-output rendering | 2 to 4 days |
| Polished | Registry-driven discovery and install, `session/load` resume, optional read-only `fs/read_text_file`, workshop presets, Windows checks | 1 to 2 weeks |

## Risks

- **Moving targets.** ACP and the adapters change quickly (the Claude and Codex
  adapters were renamed in 2026). Keep launch commands in one table and the SDK
  pinned.
- **Prompt injection.** Conference data is public text sent to an agent with
  tools. The preamble marks it as reference material, and permissions stay
  manual, but that is mitigation, not a guarantee.
- **Cost and side effects.** The agent spends your model quota and acts in
  `--cwd`. Permission prompts are the safety net; point `--cwd` at a scratch
  directory for demos.
- **Agent differences.** Some agents only ask permission for some tools, or
  apply their own approval modes. `ae code` can only gate what the agent asks
  about.
- **`--npx` runs downloaded code.** It is opt-in and prints nothing secret, but
  it is still remote code execution by design.

## Out of scope

- Being an ACP **agent** (an editor driving AgentEng); MCP and A2A cover that.
- Installing agents, managing their sign-in, or storing any credential.
- Granting the agent client-side file or terminal access.
- Persistent "always allow" rules across runs.
- Hosted or remote agents (ACP over HTTP); stdio only.
- Sending anything to AgentEng organizers. `ae code` is local only.
