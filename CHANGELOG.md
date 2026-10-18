# Changelog

## Unreleased

- Catalogue re-exported from site commit b7c271d: the London 2026 talk "Debugging and Optimizing Voice Agents" did not take place, so it and its speaker card are removed. London now lists 9 talks and 17 speakers across 11 events. The "Who is speaking?", "When and where was the conference?" and "How is this different?" FAQ answers follow the site (nine technical talks). The talk is gone from the agenda, gallery, talks, search and bingo terms, and the website command fixture drops its speaker command. Its old gallery slug returns not_found; the site redirects that page to /london-2026/videos.

## 0.0.26 - 2026-10-18

- Catalogue re-exported from site commit 1072362: the London 2026 recordings are public. "Will talks be recorded?" now answers "Yes. Recordings are public and published on https://agentengineering.world/london-2026/videos as they become available, starting with the welcome video.", and the day guide's photography and content section says the same. The previous wording limited recordings to ticket holders.
- Plain-English questions such as "Will talks be recorded?" and "Are the talks recorded?" now return that published answer instead of a talk-topic miss.
- Catalogue re-exported from site commit 4e34c4b: the Harness Engineering San Francisco video is an event recap, not a recording. It is now `sf-harness-engineering-2026-recap` (`/gallery/sf-harness-engineering-2026-recap`), titled "Harness Engineering San Francisco: event recap", with the summary "Recap of our Harness Engineering evening in San Francisco, attended by 300+ members."
- Event recaps are their own kind, `event-recap`, in `agenteng gallery`, `agenteng recordings` and talk payloads, shown as "Event recap". The four Harness Engineering San Francisco sessions in `agenteng talks` no longer point to it as their recording. `agenteng gallery sf-harness-engineering-2026-full-event` still resolves to the recap.

## 0.0.25 - 2026-10-18

- Catalogue re-exported from site commit e968fc9, which moves the London 2026 conference under `/london-2026`. Sources and answers now link to `/london-2026/speakers`, `/london-2026/agenda`, `/london-2026/guide`, `/london-2026#faq` and `/london-2026` (formerly `/#venue`, `/#agenda` and `/#tickets`). London's post-event behaviour is unchanged, and San Francisco stays upcoming.
- Catalogue re-exported from site commit 8cd5a6a, which renames the talks page to the gallery: links use `/gallery` and `/gallery/<slug>`, and `/london-2026/videos` is the new London recordings page.
- New `agenteng gallery` mirrors `/gallery`: the London 2026 recordings (the welcome video, then 10 talks marked "Recording coming soon") and the Harness Engineering San Francisco full-event recording. `--city`, `--event`, `--topic`, `--search`, `--speaker`, `--a2a` and `--limit` filter it, and `agenteng gallery <slug>` reads one item. Rows carry `slug`, `gallery`, `status`, `youtube_id`, `video_url` and `talk_url`; transcripts appear only when the site publishes one (none today). New `gallery` operation and `agenteng-gallery` agent card skill.
- `agenteng talks` lists the speaker programme with full abstracts: AgentEng London 2026, Code Engineering San Francisco (linked to `/san-francisco`, which has no gallery pages) and the Harness Engineering San Francisco sessions, with the same `--city`, `--event`, `--topic`, `--search`, `--speaker` and `--limit` options, and `agenteng talks <slug>` reads one talk. The `agenteng-talks` skill describes this split.
- A2A talks stay low-key: `agenteng gallery` lists them only with `--a2a` or `--city Online`, after the event videos, labelled AI-generated and with the A2A disclaimer; `agenteng talks` and general search never list them. `agenteng a2a-talks` is unchanged.
- `agenteng recordings` adds the London 2026 recordings page, the London welcome video and the Harness Engineering San Francisco full event, and says the London talk recordings are coming soon.
- Code Engineering San Francisco (27 October 2026): speaker roles, companies and X links come from the site's `sf-code-engineering.ts`, and the event card lists the four speakers. Event cards and JSON add `page_url` and the speaker `lineup`.
- Discovery and `agenteng about` add the gallery, the London 2026 recordings page, the CLI page, AgentEng London 2026 and the next and previous editions from the site's `events.ts` (Agent Engineering San Francisco, April 2027, and London 2026).
- `agenteng disciplines` lists all 14 site disciplines from `disciplines.ts`, with tool counts where the directory has listings; Factory Engineering and Decision Engineering are marked "no tool listings yet". `agenteng themes --disciplines` is an alias, and the website forms `agenteng --themes` and `agenteng --list-disciplines` both run it. `agenteng themes` stays the four London programme tracks.
- The next edition, Agent Engineering San Francisco, is labelled "coming April 2027" with no date or venue. The discovery prompt "Find the next Agent Engineering Conference in London" becomes "What is the next Agent Engineering event in San Francisco?", taken from the site's next event, and the answer names the next San Francisco event and the April 2027 conference.
- The `talks` operation (REST, MCP and A2A) takes `city`, `topic` and `include_a2a`, and `talk` takes a talk slug as `session_id`. New `agenteng-talks` agent card skill.
- Website command check: commands on `/london-2026`, `/gallery` and `/agenteng` are in the fixture, and prose literals that end like a sentence are no longer read as commands.

## 0.0.24 - 2026-10-17

- Catalogue re-exported from site commit a3cd566, the post-event pass for AgentEng London (16 October 2026). The FAQ is regenerated from the site, so the team seats, approval, refund and dietary answers are gone, and the remaining answers read in the past tense. The export no longer requires the homepage "Best way in" and registration lines, which the site removed; registration wording now comes from the day guide.
- Past-event behaviour is date-driven from the event's published end time:
  - `agenteng tickets london` and the event's `registration_note` say "The event was fully booked." with no day guide pointer.
  - The agenda answer reads "This is the published agenda from 16 October 2026."
  - `agenteng venue london` hides the times and the help block.
  - Event and ticket cards label a past event's link "Event page:" instead of "Register:".
  - The interactive menu labels the guide "Day guide (archive)" and removes the live now/next board; the guide card is titled "Day guide (archive)".
  - The discovery prompt becomes "Show the AgentEng London 2026 programme".
  - Time answers never say "Now:" or "Next:": "Who is speaking at 10:00?" answers "At 10:00 on 16 October 2026: <talk> (presented by <speaker>).", and now/next questions say the event has ended and point to the published agenda.
- Plain-English questions fall back to the London event once it is over: doors and arrival questions answer in the past tense ("Doors opened at 08:00 ..."), agenda, programme and ticket questions use London, talk answers say "presented" and "Held on", and guide topics point to the archived day guide. San Francisco questions are unchanged.

## 0.0.23 - 2026-10-15

- First PyPI release of the 0.0.22 changes below. 0.0.22 was tagged but never published to PyPI, because its release check hit an intermittent Python 3.12 crash after the tests passed.
- Tests: the suite collects and freezes garbage once all results are reported, avoiding a protobuf (upb) segfault in Python 3.12's final garbage collection. Test outcomes are unchanged.

## 0.0.22 - 2026-10-15 (not published to PyPI)

- New `agenteng a2a-talks` (and the website badge `agenteng --agent-to-agent`) lists the Agent-to-Agent (A2A) Talks from site commit 79be9bf: 10 short AI-generated videos with titles, YouTube links, 00:30 durations and discipline tags. `--topic` filters by tag and `--json` gives the structured result.
- The same list is available as the `a2a-talks` request operation over REST, MCP and A2A, with a new `agenteng-a2a-talks` agent card skill. The A2A protocol is unchanged.
- Every answer carries the published disclaimer: "These videos are produced by the Agent Engineering team using AI. They are separate from the conference programme and are not created, reviewed or endorsed by our speakers." The videos never appear in speakers, talks or the agenda, and general search and chat leave them out unless the question names A2A or Agent-to-Agent.

## 0.0.21 - 2026-10-15

- Catalogue re-exported from site commit 094ab77: the after-event social now reads "Details will be shared during the day. Drinks are buy your own.", and the agenda and FAQ say "Informal networking from 16:30. Details shared on the day."

## 0.0.20 - 2026-10-15

- Catalogue re-exported from site commit 84f1011: the ticket FAQ is now "Can I still get a ticket?" with fully booked wording, and the team seats answer is updated.
- Plain-English `ask`, `chat` and A2A text questions about every day guide topic now answer from the matching guide section, defaulting to the upcoming London event: lunch, food, drinks and coffee; the bar and social area; the speaker area; Q&A; photography; phones and laptops; seating; help and contacts; and the after-event social (not the sponsorship option). "Where is ...?" questions about these topics no longer fall back to the events list.
- "What is the next talk?", "What's on now?" and "Who is speaking at 10:00?" use the now, next and agenda-at-time lookups. Speaker-name questions such as "Who is Alexander Korchagin?" lead with the speaker card.
- For fully booked events the old ticket FAQ (Luma purchase and prices) is no longer offered as a search excerpt, and the ticket terms source is no longer cited anywhere.
- `agenteng ask` in a terminal renders cards for every answer shape (guide sections, quick facts, directions, now and next, speaker, registration, tools, participation) with no raw JSON. `--json` output is unchanged.
- "Is there wifi?" stays an honest search: nothing about wifi is published.

## 0.0.19 - 2026-10-15

- Plain-English `ask`, `chat` and A2A text questions with no city now default to the upcoming London conference while it is upcoming or today. Named San Francisco questions are unchanged.
- "When do doors open?" and "What time does it start?" answer from the day guide: doors 08:00, arrive 8:30 to 8:45, be seated by 8:50, programme starts 9:00 sharp, citing the quick facts and arriving section.
- "How do I get to the venue?" and "How do I get to Everyman?" answer with the address, the best way in via Canary Wharf Elizabeth line station and the walk video, citing the getting here section.
- "Where is registration?" answers "Registration is on the left as you walk in." with the registration and badges section.
- "Are tickets available?", "Can I still buy a ticket?" and "Is London sold out?" give the site's fully booked wording without the old ticket terms source.
- The agenda answer for a fully booked event no longer says attendance is subject to registration.

## 0.0.18 - 2026-10-15

- New `agenteng guide` command and public `guide` operation (CLI, HTTP, MCP and A2A) mirroring the website's /guide day guide for AgentEng London on Fri 16 October 2026: quick facts, arriving, getting here, registration and badges, social area, speaker area, lunch and drinks, questions and Q&A, photography, phones and laptops, seating, help on the day and the after-event social. `agenteng guide SECTION`, `--section`, `--list` and `--json` are supported; the website wording `agenteng guide --london` works too. The A2A event-day skill, MCP instructions, interactive menu and rich terminal cards include it.
- `agenteng venue` for London adds the published directions: best way in via Canary Wharf Elizabeth line station, the walk video (https://www.youtube.com/watch?v=GPmvi7qjiwA), registration on the left as you walk in, doors 08:00, arrive 8:30 to 8:45, be seated by 8:50, programme starts 9:00 sharp, plus the day-guide help contacts.
- `agenteng about` and the London event card show the homepage tagline "There are many Agent conferences. This one is truly yours." and the "Why this one is truly yours" text.
- Tickets are no longer promoted. London is fully booked, so `agenteng tickets london` prints the site's wording and points to the day guide, with no prices or registration link; the event card, interactive menu and fallback hints no longer prompt for tickets.
- `scripts/export-website.mjs` exports the guide, directions, tagline and registration status from the site source (site commit 9a899d8), with drift checks on guide sections, venue, times, help links and the homepage ticket section. Imported text has em dashes stripped.

## 0.0.17 - 2026-10-12

- Data: associate name corrected to Gloria Gong in `agenteng about`.

## 0.0.16 - 2026-10-11

- Sync the bundled catalogue with agentengineering.world (site commit fe27241) via `scripts/export-website.mjs`. Alexander Korchagin, Head of Technology Adoption at JetBrains, replaces the previous JetBrains speaker in the 09:15 to 09:45 London slot and the same lineup position, with the talk "Agentic Coding in 2026: Watching 300 Engineering Orgs adopting agents" (`agenteng speaker alexander-korchagin`, `agenteng talk alexander-korchagin`).
- `agenteng about` and `agenteng about --organiser` / `--chair` list the associates published on the homepage chair card (James Hua, Gloria Gong). Media support credits from the /support page are not included.
- The support page moved from /sponsorships to /support; catalogue sources now cite https://agentengineering.world/support. The recording support blurb follows the site's new wording.
- The exporter orders its speaker list by the site's `listedOn` date when present, matching the website's lineup order.

## 0.0.15 - 2026-10-07

- Add the conference's travel/accommodation funding policy and visa invitation letter policy to the attributed FAQ catalogue.
- Route travel, accommodation and visa questions to practical FAQ evidence, including questions about speakers' costs, without requiring a model.

## 0.0.14 - 2026-10-07

- Answer topical speaker and session questions directly from the published programme, including conversational wording and the reported memory-engineering question.
- Return cited speakers, talk titles and local session times without AI calls, provider quota or outage banners. Preserve city, event and cancellation filters and existing company-based speaker searches.
- Verify the reported question through the website's A2A transport and during provider cooldown; do not invent unpublished talks.

## 0.0.13 - 2026-10-07

- Add real A2A, MCP and ACP connection setup commands and validate website CLI examples against the tool.
- Public-only scope: remove bookmarks, personal planning, proposal drafting and private intake across CLI, HTTP, MCP and A2A. Legacy intake settings no longer enable storage.
- Fix cancelled-event now/next and doors-opening lookup without a model.
- Preserve published session IDs across running-order edits; refresh dependencies and public command documentation.

## 0.0.12 - 2026-10-06

### Fixed

- Conversational questions such as "How are you?" and thanks receive direct replies without catalogue searches or inference. Identity, agent engineering definitions and setup questions have focused public fallback answers.
- General chat search ignores conversational filler, requires meaningful source overlap, and excludes attendance FAQs unless the visitor asks an attendance question. Fallback returns concise evidence rather than an unrelated search-card dump.
- When the question already has supporting evidence, request a final JSON answer directly instead of enabling unnecessary tool calls. Missing-evidence questions retain a bounded lookup round; FAQ is absent from their tool schema unless relevant and irrelevant FAQ calls are rejected.
- Source citation, unpublished-contact and credential checks, provider privacy settings, model budgets and outage fallback remain enforced.

## 0.0.11 - 2026-10-06

### Fixed

- Public chat prioritizes the question's existing evidence, uses a smaller overview, and limits missing-fact lookups to one round instead of repeatedly searching broad FAQs.
- Reply cards come from the records actually cited, so a final unrelated lookup cannot replace the speaker or tool cards supporting an answer.
- Reviewed, attributed MCP, A2A and ACP explanations remain useful without a model. Greetings need no model calls, and short follow-ups reuse the recent question.
- Accept JSON fenced by a model while keeping source membership and privacy checks. Invalid model output gets a short cooldown; provider quota and outage cooldowns remain conservative.
- Static fallback includes only a bounded reason code, never provider exception text, prompts or credentials.

## 0.0.10 - 2026-10-06

### Fixed

- Public chat refuses requests containing common unpublished email/phone identifiers, credential patterns, self-disclosed personal details or requests for private records before any provider call. Checks recent user/assistant history as well. These checks are not a complete personal-data detector.
- Reject model output containing unpublished email/phone identifiers or credentials even when its source IDs pass citation validation. Published organizer contact details remain available.
- OpenRouter public-chat calls require `provider.data_collection=deny` and `provider.zdr=true`. If no eligible free endpoint is available, the existing lookup fallback remains in use; privacy requirements are never relaxed.
- Verify public A2A and captured model requests against a synthetic private proposal database, including malicious private receipt requests. Private records remain unchanged and absent from public responses and model prompts.

### Documentation

- Correct the privacy guide to describe chat processing, external providers, hosting-platform request metadata, common-identifier checks and their limitations. No blanket claim that all free-text personal data can be detected.

## 0.0.9 - 2026-10-06

### Added

- Opt-in public `chat` operation for the website and A2A, configured with `AGENTENG_ENABLE_CHAT=1` and the existing model provider variables. Supports OpenRouter-compatible chat completions, up to six recent conversation messages, and a bounded loop over public catalogue tools.
- Automatic lookup fallback when chat is disabled, unconfigured, busy, quota-limited, slow, or returns invalid output. Provider failures trigger a five-minute per-process cooldown; each question uses at most three provider calls and four public lookups. At most five model questions per minute are admitted per process.
- Website chat capability advertised in the A2A agent card and `chat_enabled` in health output. No server-side conversation retention, private operations, bookmarks, arbitrary network access or code execution in public chat.

### Changed

- Cloud Run tag deployments update the public origin without replacing operator-configured environment variables or secret references. Container defaults keep chat, standard inference, RLM and private intake disabled until explicitly enabled.
- Standard and RLM engines remain operator-only. Public chat has its own explicit activation and never grants operator or participant access.

## 0.0.8 - 2026-10-06

### Changed

- `docs/COMMANDS.md`: a full command reference for every visible command and subcommand, with options, examples, the Result JSON fields, the commands that print other output, and exit codes. A test keeps it complete.
- Every visible option now has `--help` text, and commands with arguments explain them.
- User-facing copy says `agenteng` instead of `ae` (about `connect_commands`, the bingo `command` and card footer, `now --screen` help, the save error, the live board footer, `agenteng code` messages and the installer's next steps). `ae` remains the short developer alias.
- Empty but valid results (no bookmarks in `my-agenda`, nothing on in `now`, zero `search` hits, an empty `talks --search`) now exit `0` in the CLI. Unknown IDs still exit `1`. The Result JSON is unchanged, so MCP, A2A and HTTP clients see the same `status`.
- Docs: installer environment variables, `AGENTENG_OUTPUT` and `AGENTENG_CONFIG_DIR` in `.env.example`, `agenteng` in doc examples, and the bingo skill text now says the card is in `data` with printable formats in `artifact`.

### Fixed

- Allow the A2A 1.0 version header in browser CORS preflights so the website chat can reach the live agent. Untrusted origins remain blocked.
- Route natural-language speaker questions to the public speaker catalogue while preserving city and company filters.

### Documentation

- Document the website A2A chat and explicit local development origins. Browser requests use public catalogue lookup without inference or private intake.

## 0.0.7 - 2026-10-06

### Added

- `agenteng live` (also `agenteng now --screen`): a full-screen, auto-refreshing now/next board for venue screens with the event title, venue and track, a large clock, the current talk with a progress bar, next up and later sessions. `--event`, `--refresh SECONDS`, `--at` (ISO time or `HH:MM` on the event day; the clock runs forward from it) and `--once`. Piped or with `--json` it prints one Result JSON snapshot. New `live` operation for MCP, A2A and HTTP; `now` and `next` also accept `at`.
- `agenteng bingo`: talk bingo cards (5x5 with a free centre, or 4x4) built only from terms that appear in the event's published talk titles, abstracts and agenda, plus the speakers' published disciplines. `--seed` makes cards reproducible and is printed on every card; `--format text|svg|html` and `--output` give printable cards; `--play` marks squares in the terminal and calls bingo. New `bingo` operation; local only, nothing is sent.
- `agenteng about` (organiser, conference chair, links and how to connect agents: install line, remote MCP URL, agent card) and `agenteng hq [manifesto|mindset|reading]` (Agent Engineering HQ content). Both come from published website data, exported by `scripts/export-website.mjs` into new `about` and `hq` catalogue records with source evidence.
- Website command wording: city slugs (`--city san-francisco`, `sf`, `london`) for every city filter including MCP and A2A requests, `events [CITY]`, `events --next` / `--history` / `--previous`, hidden `--london` / `--sf` shortcuts, city names as event IDs (`agenteng agenda london`), `agenteng --list-disciplines`, `agenteng --themes`, `agenteng --list-cities`, `agenteng --info`, `agenteng inspect --speaker SLUG` and `agenteng whoami --chair`. Existing commands and JSON are unchanged. The short `ae` alias works the same for local developer convenience; website copy always shows `agenteng`.
- `docs/SITE-SYNC.md` and `tests/fixtures/site_commands.tsv`: all 45 commands shown on agentengineering.world with their status; CI runs every row. 17 run after this change (3 in 0.0.6).
- Menu entries for the live board, talk bingo, about and Agent Engineering HQ; an `agenteng-event-day` A2A skill.

### Fixed

- The remote MCP server reports the agenteng version in `serverInfo` instead of the MCP SDK version.
- `--remote` requests omit default fields so a newer CLI keeps working against an older server.
- Privacy: a new config directory and `acp-logs/` are created `0700`; bookmarks are written `0600` from the start (atomic replace). `agenteng serve` no longer writes per-request access lines (client address, path) unless `--access-log` is passed. New privacy section in `docs/DATA.md`.
- README and docs: `agenteng --json events` (global options go before the command) and a working `--catalogue` example with export instructions.

### Documentation

- Site sync guide: conference website command examples always use `agenteng`, never the `ae` alias.

## 0.0.6 - 2026-10-06

### Added

- Experimental `ae code` ACP client in the new optional `agenteng[acp]` extra (official `agent-client-protocol` Python SDK). It launches an Agent Client Protocol coding agent (Claude Code and Codex adapters, Gemini CLI, Copilot, Cursor, OpenCode, goose, Qwen Code, fast-agent, Kimi, or any `--agent-command`), attaches the AgentEng MCP server to the session, adds talk, event, speaker or tool records named in the prompt, and streams messages, tool calls and plans as rich output or `--json` events. `ae code --list` shows which agents are on `PATH`. Every permission request is asked in the terminal and rejected without one; nothing is auto-approved. See `docs/ACP.md`.
- `ae code` chat mode: with no prompt in a terminal, or with `--chat`, one ACP session stays open across turns. Ctrl-C sends `session/cancel` (also at a permission prompt), Ctrl-D or `/exit` ends the chat, and `/help`, `/context ID` and `/agent` are available. `--chat` with piped stdin runs one turn per line; `--json` alone stays single-shot.
- "Code with an agent (ACP, experimental)" in the `ae` menu: pick an installed agent (or see install hints) and optionally a talk, then chat.
- Diffs in `ae code`: ACP diff content renders as coloured unified diffs in permission prompts and tool-call streams, truncated after 40 lines with a "view the full diff" option; `--json` permission events add a `diffs` summary.

### Fixed

- `ae talk SESSION_ID` resolves exact session IDs such as `agenteng-london-2026-14` instead of returning a text-search match.

### Changed

- Default the Cloud Build `_PUBLIC_URL` substitution to `https://a2a.agentengineering.world`, so tag deploys keep the custom domain instead of resetting `AGENTENG_PUBLIC_URL` to the generated `run.app` URL (which made the custom domain return `400 Invalid host header`). Forks can set `_PUBLIC_URL` empty or to another origin on their trigger.

### Documentation

- Only the `push-new-tag` Cloud Build trigger should deploy. The deployment guide now has console and `gcloud` steps to disable the Cloud Run wizard branch trigger.

## 0.0.5 - 2026-10-05

### Added

- Native `ae` console-script alias alongside `agenteng`.
- Rich human-readable TTY output (cards and tables), with auto JSON for agents via `--json`, `AGENTENG_OUTPUT=json`, or piped stdout.
- Interactive `ae` / `agenteng` menu (questionary) for browsing events, search, tools, proposals and agent connection.
- Full website content parity: talk abstracts, speaker bios and links, FAQ, venue, sponsors, code of conduct, and program themes.
- Local engagement helpers: `now` / `next`, `save` / `unsave` / `my-agenda` bookmarks, and `agenda --format ics` export.

## 0.0.4

### Changed

- Replace the wheel-mirror installer with a branded, SuperQode-style AgentEng installer: an animated purple and blue terminal intro, then `uv tool install` of the latest `agenteng` from PyPI with the `server` extra (MCP and A2A included). It bootstraps uv when missing, falls back to a user virtualenv with pip, never uses sudo, and upgrades on re-run. `AGENTENG_VERSION` and `AGENTENG_EXTRAS` override the defaults.
- Advertise the one-line installer at `https://a2a.agentengineering.world/install.sh`, which serves the script as plain text, until the conference site allows non-browser access to `/install.sh`.
- Release metadata checks now require the installer to stay version-free, install from PyPI and never download wheels from the website `/releases/` mirror.

### Documentation

- Mark the hosted A2A agent live at `https://a2a.agentengineering.world` and list its public endpoints.
- Add "Invalid host header" troubleshooting to the deployment guide and explain why `_PUBLIC_URL` must stay set on the Cloud Build trigger.

## 0.0.3

### Fixed

- Install Git in the Cloud Build verification image so the Git-ignore release test can run; trust only the shared `/workspace` checkout across builder containers.
- Include Git error output when the ignore-rule test fails, instead of reporting only mismatched paths.

## 0.0.2

### Changed

- Reject invalid public URLs at startup with a clear configuration error, instead of failing requests in host-validation middleware.

- Default the Cloud Run service name to `agenteng`; document the trigger override for the published `v0.0.1` tag.

## 0.0.1

### Changed

- Align the initial package and installer release to `0.0.1`; derive the HTTP API version from package metadata and show the expected tag in release-check failures.

- Use `agenteng` as the Python package distribution name, matching the CLI and module.

### Added

- Tag-triggered Cloud Build deployment with release validation, generated Cloud Run URL setup, dedicated runtime identity, live MCP/A2A checks and a console setup guide.

- Minimal Markdown documentation with the official logo and favicon, MkDocs Material preview and GitHub Pages publishing.

- Version-tag PyPI publishing and GitHub releases using verified CI artifacts, with release metadata validation and existing-tag retry support.

- Offline tool directory: 456 listings covering 461 attributed source entries across twelve disciplines; CLI/MCP/A2A list, search, filters, aliases and pagination, crawlable pages/feed, and validated maintainer import.

- Public event catalogue with source attribution, snapshot freshness and timezone-aware event states.
- `agenteng` CLI for events, speakers, agendas, published ticket terms, recordings, search and session/calendar planning.
- One-tool MCP server over stdio and Streamable HTTP; A2A 1.0 discovery and JSON-RPC adapter.
- Optional ordinary synthesis and Monty RLM, disabled by default, with one child or leaf delegation and depth one.
- Versioned wheel installer, release staging, Cloud Run configuration and local/CI verification.
- Read-only participation guidance for talk and event ideas, with explicit organizer discretion.
- Apache-2.0 license, contributor/security/community documentation and GitHub issue forms.
- London/San Francisco discovery, source-backed invited-programme policy, crawlable event pages/JSON-LD, event feeds and agent/crawler guides.
- Codex, Claude Code, Cursor and generic MCP connection instructions plus a remote stdio bridge.
- Guided offline drafts, completeness checks and private-permission JSON/Markdown export.
- Opt-in single-organizer SQLite intake pilot: participant credentials, confirmed previews, durable receipts, scoped status/history, withdrawal, retention and local organizer review.

Hosted intake remains disabled by default and requires persistent private storage; the supplied Cloud Run configuration serves public discovery/drafting.
