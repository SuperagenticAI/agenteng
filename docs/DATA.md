# 📖 Data and attribution

The bundled catalogue contains public Agent Engineering HQ event information: event titles, venues, published dates, speaker listings with links and talk abstracts, agenda entries, FAQ answers, sponsors and support options, program themes, code of conduct summary, ticket terms and links to registration or recordings. It includes no attendee/member exports, private contact list or proposal submissions.

The software license covers this project's source code and original documentation. It does not grant rights to third-party biographies, talk abstracts, names, logos, photographs or recordings. Such material remains attributed to its public source and subject to any rights held by its owner. Linked videos are not downloaded or redistributed by this project.

Every catalogue record references a public source. An export records its publication time, source revision and content hash. The catalogue is a snapshot: it does not verify live ticket availability, registration approval, cancellation or changes made after export. Consult the linked registration/event page for current details.

Historical events with only a month published retain month precision. Unknown session times and ticket expiry dates are not filled in. Calendar export only uses sessions with published start and end times.

For a correction or removal request, contact [events@agentengineering.world](mailto:events@agentengineering.world) with the record and source URL. Maintainers can update the catalogue after checking the source. When updating data, preserve attribution and avoid adding private information or copyrighted assets without authorization.

## Privacy

AgentEng holds no personal data about its users and collects none.

- **No telemetry.** The CLI makes no network calls unless you pass `--remote URL`, which sends only the typed request you ran (for example `{"operation":"events","city":"London"}`) to that host. It sends an `Authorization` header only if you set `AGENTENG_OPERATOR_TOKEN` or `AGENTENG_PARTICIPANT_TOKEN` yourself; only set those for a host you trust.
- **Local files stay local.** Bookmarks (`save`, `my-agenda`) and `agenteng code` agent logs live in the AgentEng config directory (`$AGENTENG_CONFIG_DIR`, else `$XDG_CONFIG_HOME/agenteng`, else `~/.config/agenteng`). They are never uploaded. A new config directory and the `acp-logs/` folder are created `0700`, and bookmark and log files `0600`.
- **`agenteng code` logs can contain personal text.** `acp-logs/*.log` holds each coding agent's stderr, which may echo your prompts, file paths or account names. Delete the folder any time: `rm -rf ~/.config/agenteng/acp-logs`. `agenteng code` does not read or send your files. Prompts go to the coding agent you chose (and its provider), never to AgentEng's server. Talk context comes from the local catalogue, and the attached MCP server is a local `agenteng mcp` process.
- **Hosted service.** The public MCP, A2A and HTTP service reads no client addresses, and no headers apart from `Authorization` and `Origin` (for CORS). It keeps no conversations or request bodies. It writes no per-request application log: `agenteng serve` disables the access log unless you pass `--access-log`. The hosting platform (Cloud Run) keeps its own standard request log (time, path, status, client address and user agent), which AgentEng does not control.
- **Proposals** stay local drafts unless an operator enables private intake and you explicitly confirm a submission. The public deployment keeps intake disabled.

## Tool directory

Tool names and public links are factual metadata attributed to a pinned SuperRadar snapshot. AgentEng supplies its own classifications and normalization; source descriptions, rankings and imagery are not copied. `source_listed` metadata is not independently verified adoption evidence. Listings retain source aliases and provenance; see [directory usage and refresh](TOOLS.md). Third-party trademarks, assets and software retain their own rights.
