# Site command sync

Every `agenteng` command shown on [agentengineering.world](https://agentengineering.world)
(website source `src/`), with what it does in the CLI today. This page is for keeping
the website and the tool in step, in stages: the website owns its copy, the CLI owns
what runs.

The same list lives in
[`tests/fixtures/site_commands.tsv`](https://github.com/SuperagenticAI/agenteng/blob/main/tests/fixtures/site_commands.tsv),
and CI runs every row: a command marked as working must exit 0, a command marked
"site text should change" must still fail and its replacement must exit 0, and a
command marked "not built" must fail. When the site adds or rewords a command, add or
edit its row in that file and this page.

The website always writes commands as `agenteng ...`. The short `ae` alias is a
convenience for developers in their own terminal and is never used on the site.

## Summary

| | Count |
| --- | --- |
| Distinct commands on the site | 45 |
| Worked in 0.0.6 | 3 |
| Work after stage 1 (works now + aliases) | 17 |
| Real command exists; site text should change | 17 |
| Not built | 11 |

Status meanings:

- **works now**: runs exactly as printed on the site, before and after stage 1.
- **alias added in stage 1**: runs exactly as printed; the CLI accepts the site's wording and returns the same JSON as the canonical command.
- **site text should change**: a real command exists. Replace the site text with the command in "Run this".
- **not built**: no catalogue data or command behind it. Restyle as a heading, or mark it illustrative.

## Every site command

| Site command | Site file (`src/`) | Status | Run this | Note |
| --- | --- | --- | --- | --- |
| `agenteng --help` | `components/FAQSection.tsx` | works now | `agenteng --help` |  |
| `agenteng speakers` | `pages/Agenda.tsx` | works now | `agenteng speakers` |  |
| `agenteng events --city london` | `pages/London.tsx` | works now | `agenteng events --city london` |  |
| `agenteng events --city san-francisco` | `pages/SanFrancisco.tsx` | alias added in stage 1 | `agenteng events --city san-francisco` | city slugs accepted everywhere a city is |
| `agenteng events --next san-francisco` | `pages/SanFrancisco.tsx` | alias added in stage 1 | `agenteng events --next san-francisco` | --next = --upcoming; optional CITY argument |
| `agenteng events --london --next` | `pages/London.tsx` | alias added in stage 1 | `agenteng events --london --next` | --london / --sf shortcuts for --city |
| `agenteng events --london --history` | `pages/London.tsx` | alias added in stage 1 | `agenteng events --london --history` | --history = --past |
| `agenteng events --previous` | `components/SFProofBand.tsx` | alias added in stage 1 | `agenteng events --previous` | --previous = --past |
| `agenteng agenda --london` | `pages/Agenda.tsx` | alias added in stage 1 | `agenteng agenda --london` | city resolves to its next event |
| `agenteng tickets --london` | `components/TicketsSection.tsx` | alias added in stage 1 | `agenteng tickets --london` |  |
| `agenteng sponsors --sf` | `components/SponsorStrip.tsx` | alias added in stage 1 | `agenteng sponsors --sf` |  |
| `agenteng inspect --speaker samuel-colvin` | `components/SpeakerAgentActions.tsx` | alias added in stage 1 | `agenteng inspect --speaker samuel-colvin` | hidden alias of agenteng speaker SLUG |
| `agenteng --themes` | `components/CoreThemesSection.tsx` | alias added in stage 1 | `agenteng --themes` | runs agenteng themes |
| `agenteng --list-disciplines` | `components/WhatIsAgentEngSection.tsx` | alias added in stage 1 | `agenteng --list-disciplines` | runs agenteng disciplines |
| `agenteng --list-cities` | `pages/AgentEngineeringHQ.tsx` | alias added in stage 1 | `agenteng --list-cities` | runs agenteng discover (cities and featured events) |
| `agenteng --info` | `components/Footer.tsx` | alias added in stage 1 | `agenteng --info` | runs agenteng about |
| `agenteng whoami --chair` | `components/FounderCLISection.tsx` | alias added in stage 1 | `agenteng whoami --chair` | hidden alias of agenteng about --chair |
| `agenteng agenda --preview` | `components/AgendaPreviewSection.tsx` | site text should change | `agenteng agenda --london` |  |
| `agenteng conference --london` | `pages/London.tsx` | site text should change | `agenteng event --london` |  |
| `agenteng speakers --announced` | `components/SpeakersAnnouncedSection.tsx` | site text should change | `agenteng speakers` | every listed speaker is announced; a no-op flag would be decorative |
| `agenteng list --speakers` | `pages/Speakers.tsx` | site text should change | `agenteng speakers` |  |
| `agenteng venue --info` | `components/VenueSection.tsx` | site text should change | `agenteng venue --london` |  |
| `agenteng faq --search` | `components/AgentActivityPanel.tsx` | site text should change | `agenteng faq --search recorded` | --search needs a query |
| `agenteng plan --program` | `components/ProgramTracksSection.tsx` | site text should change | `agenteng plan --london --interest memory` |  |
| `agenteng schedule --optimize` | `components/AgentActivityPanel.tsx` | site text should change | `agenteng plan --london --interest memory` |  |
| `agenteng contact --options` | `components/CTASection.tsx` | site text should change | `agenteng participate` |  |
| `agenteng compare --why-different` | `components/WhyDifferentSection.tsx` | site text should change | `agenteng faq --search different` |  |
| `agenteng read --file manifesto.md` | `components/ManifestoSection.tsx` | site text should change | `agenteng hq manifesto` |  |
| `agenteng mindset --principles` | `components/AgentEngineeringMindsetSection.tsx` | site text should change | `agenteng hq mindset` |  |
| `agenteng read --further` | `components/FurtherReadingSection.tsx` | site text should change | `agenteng hq reading` |  |
| `agenteng hq --init` | `components/HomeHeroSection.tsx` | site text should change | `agenteng hq` |  |
| `agenteng hq --subscribe` | `pages/SanFrancisco.tsx` | site text should change | `agenteng events --sf --next` | registration links are in the event records |
| `agenteng hq --city san-francisco` | `pages/SanFrancisco.tsx` | site text should change | `agenteng events --city san-francisco` |  |
| `agenteng init --conference 2026` | `components/HeroSection.tsx` | site text should change | `agenteng event --london` |  |
| `agenteng --ecosystem` | `components/EcosystemSection.tsx` | not built |  | no ecosystem data in the catalogue; restyle as a heading or mark illustrative |
| `agenteng map --convergence` | `components/EngineeringConvergenceSection.tsx` | not built |  | interactive site map only; restyle or mark illustrative |
| `agenteng orchestrate --mode=live` | `components/AgentOrchestrationSection.tsx` | not built |  | animation only; restyle or mark illustrative |
| `agenteng audience --london` | `components/CommunityStatsBrief.tsx` | not built |  | community stats are not in the catalogue |
| `agenteng community --london` | `components/LondonCommunityBand.tsx` | not built |  | community stats are not in the catalogue |
| `agenteng --community --signal` | `components/CommunitySection.tsx` | not built |  | community stats are not in the catalogue |
| `agenteng identify --audience` | `components/AudienceSection.tsx` | not built |  | audience copy only; restyle as a heading |
| `agenteng --match-audience` | `components/AgentActivityPanel.tsx` | not built |  | animation only; restyle or mark illustrative |
| `agenteng run --sandbox monty` | `data/speaker-stack.ts` | not built |  | speaker demo panel; label as the speaker's own stack or use agenteng talk SLUG |
| `agenteng run --guard` | `data/speaker-stack.ts` | not built |  | speaker demo panel; label as the speaker's own stack or use agenteng talk SLUG |
| `agenteng run --stack` | `data/speaker-stack.ts` | not built |  | speaker demo panel; label as the speaker's own stack or use agenteng talk SLUG |

## For the website, next stage

1. Replace the 17 "site text should change" commands with the "Run this" command
   (for example `agenteng read --file manifesto.md` becomes `agenteng hq manifesto`).
2. For the 11 "not built" commands, restyle them as headings or add a small
   "illustrative" marker, so every command shown as a command runs.
3. Shown nowhere on the site yet, and worth adding: the install line
   (`curl -fsSL https://agentengineering.world/install.sh | sh`), `agenteng live`,
   `agenteng bingo`, `agenteng about`, the remote MCP URL `https://a2a.agentengineering.world/mcp/`
   and the agent card `https://a2a.agentengineering.world/.well-known/agent-card.json`.

Not `agenteng` commands, fine as they are: `all_roads --lead-to agent_engineering`,
`calendar--london`, `contact--email`, `a2a discover agentengineering.world/speakers/SLUG`
(no per-speaker card is served; the real card is the agent card above) and the
speakers' own tools in `src/data/speaker-stack.ts`.

## Skipped on purpose

These wordings were not added as aliases because they would add a flag that does
nothing, or a second name for the same thing, and make the CLI harder to read:

- `speakers --announced`, `agenda --preview`, `venue --info`: every published
  speaker is announced and the commands already show the full record.
- `list --speakers`, `conference --london`, `contact --options`, `compare --why-different`,
  `plan --program`, `schedule --optimize`, `init --conference 2026`: new verbs for
  existing commands.
- `read --file manifesto.md`, `read --further`, `mindset --principles`, `hq --init`,
  `hq --subscribe`, `hq --city`: `agenteng hq [manifesto|mindset|reading]` is the one place
  for HQ content.
