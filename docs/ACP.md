# 🤝 ACP client: `ae code` (experimental)

`ae code` lets AgentEng drive a coding agent you already use (Claude Code,
Codex, Gemini CLI, Copilot, Cursor, OpenCode and others) through the
[Agent Client Protocol](https://agentclientprotocol.com) (ACP), with AgentEng
conference data attached. It is an **optional extra** and **experimental**:
the command shape, defaults and output may change between releases.

```sh
uv tool install 'agenteng[acp]'
ae code --list
ae code --agent claude "scaffold a demo of talk agenteng-london-2026-14"
ae code --agent claude          # chat: many turns on one session
ae                              # menu: "Code with an agent (ACP, experimental)"
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
        [--allow-always-option] [--chat] [--json] [PROMPT]
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
| `--chat` | Keep the session open for more turns (see [Chat mode](#chat-mode)). PROMPT, if given, is the first turn. |
| `--json` | Newline-delimited JSON events instead of rich output (also used when stdout is not a terminal). |

How the mode is picked:

| You run | Mode |
| --- | --- |
| `ae code PROMPT` | One turn, then exit (as before). |
| `ae code` in a terminal | Chat. |
| `ae code --chat [PROMPT]` in a terminal | Chat, with PROMPT as the first turn. |
| `echo "..." \| ae code` | One turn: all of stdin is the prompt. |
| `printf 'a\nb\n' \| ae code --chat` | One turn per stdin line, on one session, until EOF or `/exit`. |
| `ae code --json PROMPT` (or stdin) | One turn of NDJSON. `--json` never starts chat by itself. |
| `ae code --chat --json < prompts.txt` | NDJSON chat: one turn per stdin line. |

`--json` stays single-shot unless you add `--chat`, so scripts and other
agents that already call `ae code --json` keep their behaviour. A driver that
wants several turns pipes one prompt per line with `--chat --json`; each turn
ends with its own `stop` event, and slash commands work there too.

## Chat mode

Chat keeps one ACP session (one agent process, one `sessionId`) open across
turns, so the agent remembers earlier turns and its own edits.

- A prompt box (`you ›`) reads each message; a bottom bar lists the keys.
- Each turn streams like a single-shot run and ends with its stop reason.
- Permission prompts work exactly as in single-shot mode.
- **Ctrl-C** during a turn sends `session/cancel`; the agent stops and the
  turn ends `cancelled`, and you are back at the prompt. A second Ctrl-C
  aborts the turn locally if the agent does not answer. **Ctrl-C at a
  permission prompt** also cancels the turn: the request is answered
  `cancelled`, as the spec requires. Ctrl-C on an empty prompt clears the line.
- **Ctrl-D** or `/exit` ends the chat and stops the agent.
- The agent runs in its own process session, so a terminal Ctrl-C reaches
  `ae code` (which cancels politely) rather than killing the agent.

| Command | Does |
| --- | --- |
| `/help` | List commands and keys. |
| `/context ID` | Attach a talk, event or speaker record, or `tool:ID`, to your next message. |
| `/agent` | Agent name and version, ACP version, session ID, cwd, MCP servers, turn count. |
| `/exit`, `/quit` | End the chat. |

The AgentEng preamble goes with the first turn only. Later turns send just the
new message, plus any records from `/context` or IDs detected in that message.

## Menu entry

`ae` with no arguments opens the interactive menu. **Code with an agent (ACP, experimental)**:

1. lists the ACP agents found on `PATH` (the same detection as `ae code
   --list`). If none is installed, it shows the agent table with install
   commands and returns to the menu;
2. asks whether to add a talk as context. **Pick a talk** uses the event
   picker, then the event's talks (events with no talks yet are skipped);
3. opens chat mode on that agent, with the talk attached to the first message.

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
   (with [diffs](#diffs)) and plans. Ctrl-C sends `session/cancel`.
6. In chat, repeat step 4 on the same session for each message.

The `--json` stream has one object per line with an `event` field: `agent`,
`session`, `plan`, `agent_message_chunk`, `agent_thought_chunk`, `tool_call`,
`tool_call_update`, `permission`, `warning`, `error` and `stop` (other ACP
updates pass through under their own names).

## Permissions

- Every `session/request_permission` goes to you in the terminal: the tool
  title, kind, paths and input (or [diff](#diffs)), then a numbered choice.
  **Enter rejects.**
- Nothing is auto-approved, writes included. There is no allow-all flag.
- The agent's "allow always" option is hidden by default, so each write
  needs a fresh decision. `--allow-always-option` shows it for that run.
- Without a terminal (CI, pipes, another agent driving `ae code --json`), every
  request is rejected and reported as a `permission` event. With `--json` in a
  terminal, the prompt is shown on stderr.
- Rejection uses the agent's `reject_once` option, or the `cancelled` outcome
  if the agent offered none.
- Ctrl-C at the prompt cancels the whole turn (`cancelled` outcome plus
  `session/cancel`).

## Diffs

ACP tool calls can carry
[diff content](https://agentclientprotocol.com/protocol/tool-calls#diffs)
(`{"type": "diff", "path", "oldText", "newText"}`; `oldText` is null for a new
file). `ae code` renders it as a coloured unified diff with a `+added -removed`
summary:

- **In permission prompts.** The diff is shown inside the prompt, where you
  decide. Diffs over 40 lines are cut with "... N more diff lines", and the
  prompt adds **d View the full diff**, which prints the whole diff and asks
  again.
- **While streaming.** Diffs on `tool_call` and `tool_call_update` are shown
  once, when the call starts running or finishes. A diff on a call that is
  still `pending` is held back, because the agent usually asks permission next
  and the prompt shows it; the same diff is never printed twice.
- **In `--json`.** Tool-call events pass the diff content through unchanged,
  and `permission` events add a `diffs` summary
  (`path`, `added`, `removed`, `new_file`).

## Testing

CI does not need a real agent. `tests/fixtures/fake_acp_agent.py` is an ACP
agent built on the same SDK. Its first turn sends a plan, streamed text and
thoughts, a tool call that really calls the attached `agenteng mcp` server
over stdio, and an edit with diff content that needs permission. Later turns
echo attached context, and a message containing "patch" streams a second edit
whose diff arrives on `tool_call_update`. A slow mode waits for
`session/cancel`, and `FAKE_ACP_DIFF_LINES` makes the diff long enough to
truncate. Tests check:

- the `initialize` and `session/new` payloads, the MCP round trip, rendering,
  the JSON stream, reject-by-default, the allow path, the hidden allow-always
  option and sign-in errors;
- chat: one session across turns from piped lines, `/help`, `/agent`,
  `/context`, unknown commands, `/exit`, the preamble on the first turn only,
  and `--json` staying single-shot;
- cancel: `session/cancel` ends a turn `cancelled`, and Ctrl-C at a permission
  prompt answers it `cancelled`;
- diffs: colours, stats, truncation, the `d` full view, stream diffs shown
  once, and the JSON `diffs` summary;
- the menu entry: agent pick, talk pick (skipping events with no talks),
  install hints when no agent is installed.

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
| Spike | One prompt turn, agent catalogue, MCP attach, context blocks, permissions, rich and JSON output, fake-agent tests | Done |
| Usable, part 1 | Chat loop with cancel and slash commands, `ae` menu entry, diffs in permission prompts and streams | Done |
| Usable, part 2 | Session modes and model picker, better long-output rendering, slash commands advertised by the agent | 1 to 2 days |
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
