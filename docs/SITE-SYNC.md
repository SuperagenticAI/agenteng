# Website command verification

Every displayed AgentEng command must be accepted by the CLI. The hero Orchestrator demonstrates `agenteng connect a2a`, `agenteng connect mcp --transport http`, and `agenteng connect acp`, then says “Welcome to AgentEng!”. These protocol commands print usable setup instructions; the animated website panels do not execute a shell or claim live connections.

Run `python scripts/check-website-commands.py WEBSITE_REPO` against a website checkout with Node dependencies installed. It reads public TypeScript literals using the AST, validates them against the actual CLI, and executes public lookup/setup commands. Server loops and coding sessions are parsed without launching them. Dynamic speaker-profile command rendering is covered by the speaker fixture and website tests.

The fixture contains 97 command locations. Tool CI executes each row and requires success. Update it when website commands change.

| Command | Website source (`src/`) |
| --- | --- |
| `agenteng --help` | `components/FAQSection.tsx` |
| `agenteng speakers` | `pages/Agenda.tsx` |
| `agenteng events --city london` | `pages/London.tsx` |
| `agenteng events --city san-francisco` | `pages/SanFrancisco.tsx` |
| `agenteng events --next san-francisco` | `pages/SanFrancisco.tsx` |
| `agenteng events --london --next` | `pages/London.tsx` |
| `agenteng events --london --history` | `pages/London.tsx` |
| `agenteng events --previous` | `components/SFProofBand.tsx` |
| `agenteng agenda --london` | `pages/Agenda.tsx` |
| `agenteng tickets --london` | `components/TicketsSection.tsx` |
| `agenteng sponsors --sf` | `components/SponsorStrip.tsx` |
| `agenteng inspect --speaker samuel-colvin` | `components/SpeakerAgentActions.tsx` |
| `agenteng --themes` | `components/CoreThemesSection.tsx` |
| `agenteng --list-disciplines` | `components/WhatIsAgentEngSection.tsx` |
| `agenteng --list-cities` | `pages/AgentEngineeringHQ.tsx` |
| `agenteng --info` | `components/Footer.tsx` |
| `agenteng whoami --chair` | `components/FounderCLISection.tsx` |
| `agenteng agenda --london` | `components/AgendaPreviewSection.tsx` |
| `agenteng event --london` | `pages/London.tsx` |
| `agenteng speakers` | `components/SpeakersAnnouncedSection.tsx` |
| `agenteng speakers` | `pages/Speakers.tsx` |
| `agenteng venue --london` | `components/VenueSection.tsx` |
| `agenteng agenda --london --topic memory` | `components/ProgramTracksSection.tsx` |
| `agenteng participate` | `components/CTASection.tsx` |
| `agenteng faq --search different` | `components/WhyDifferentSection.tsx` |
| `agenteng hq manifesto` | `components/ManifestoSection.tsx` |
| `agenteng hq mindset` | `components/AgentEngineeringMindsetSection.tsx` |
| `agenteng hq reading` | `components/FurtherReadingSection.tsx` |
| `agenteng hq` | `components/HomeHeroSection.tsx` |
| `agenteng events --sf --next` | `pages/SanFrancisco.tsx` |
| `agenteng events --city san-francisco` | `pages/SanFrancisco.tsx` |
| `agenteng event --london` | `components/HeroSection.tsx` |
| `agenteng hq mindset` | `data/agent-activities.ts` |
| `agenteng tools --discipline memory` | `components/AgentToolingSection.tsx` |
| `agenteng connect cursor` | `components/AgentToolingSection.tsx` |
| `agenteng --agent-to-agent` (runs `agenteng a2a-talks`) | `pages/AgentToAgent.tsx` |
| `agenteng connect a2a` | `components/AgentToolingSection.tsx` |
| `agenteng connect a2a` | `data/agent-activities.ts` |
| `agenteng participate` | `data/agent-activities.ts` |
| `agenteng hq reading` | `data/agent-activities.ts` |
| `agenteng event --london` | `data/agent-activities.ts` |
| `agenteng hq` | `data/agent-activities.ts` |
| `agenteng hq manifesto` | `data/agent-activities.ts` |
| `agenteng tools --discipline eval` | `components/ProgramTracksSection.tsx` |
| `agenteng tools --discipline protocol` | `components/ProgramTracksSection.tsx` |
| `agenteng tools --discipline protocol` | `data/agent-activities.ts` |
| `agenteng tools --discipline code` | `components/ProgramTracksSection.tsx` |
| `agenteng themes` | `components/ProgramTracksSection.tsx` |
| `agenteng themes` | `data/agent-activities.ts` |
| `agenteng agenda --london --topic memory` | `data/agent-activities.ts` |
| `agenteng speakers` | `data/agent-activities.ts` |
| `agenteng speakers` | `data/speaker-stack.ts` |
| `agenteng sponsors --sf` | `data/agent-activities.ts` |
| `agenteng venue --london` | `data/agent-activities.ts` |
| `agenteng connect mcp --transport http` | `data/agent-activities.ts` |
| `agenteng connect acp` | `data/agent-activities.ts` |
| `agenteng about` | `data/agent-activities.ts` |
| `agenteng disciplines` | `data/agent-activities.ts` |
| `agenteng events --london` | `data/agent-activities.ts` |
| `agenteng events --sf` | `data/agent-activities.ts` |
| `agenteng discover` | `data/agent-activities.ts` |
| `agenteng recordings` | `data/agent-activities.ts` |
| `agenteng events --sf --next` | `data/agent-activities.ts` |
| `agenteng event --sf` | `data/agent-activities.ts` |
| `agenteng agenda --london` | `data/agent-activities.ts` |
| `agenteng conduct` | `data/agent-activities.ts` |
| `agenteng tools --discipline harness` | `data/agent-activities.ts` |
| `agenteng talks --event agenteng-london-2026` | `data/agent-activities.ts` |
| `agenteng about --chair` | `data/agent-activities.ts` |
| `agenteng about --organiser` | `data/agent-activities.ts` |
| `agenteng sponsors --london` | `data/agent-activities.ts` |
| `agenteng faq` | `data/agent-activities.ts` |
| `agenteng faq --search recorded` | `data/agent-activities.ts` |
| `agenteng speaker samuel-colvin` | `data/speaker-stack.ts` |
| `agenteng speaker andrey-breslav` | `data/speaker-stack.ts` |
| `agenteng speaker ismail-pelaseyed` | `data/speaker-stack.ts` |
| `agenteng speaker tobie-morgan-hitchcock` | `data/speaker-stack.ts` |
| `agenteng speaker alexander-korchagin` | `data/speaker-stack.ts` |
| `agenteng speaker jon-bratseth` | `data/speaker-stack.ts` |
| `agenteng speaker meryem-arik` | `data/speaker-stack.ts` |
| `agenteng speaker frederic-barthelet` | `data/speaker-stack.ts` |
| `agenteng speaker stas-bichenko` | `data/speaker-stack.ts` |
| `agenteng speaker jocelyn-darcy` | `data/speaker-stack.ts` |
| `agenteng guide --london` | `pages/Guide.tsx` |
| `agenteng event --london` | `pages/London2026.tsx` |
| `agenteng talks` | `pages/Talks.tsx` |
| `agenteng event --london` | `pages/AgentEngPage.tsx` |
| `agenteng events --next san-francisco` | `pages/AgentEngPage.tsx` |
| `agenteng speakers` | `pages/AgentEngPage.tsx` |
| `agenteng agenda --london` | `pages/AgentEngPage.tsx` |
| `agenteng guide --london` | `pages/AgentEngPage.tsx` |
| `agenteng a2a-talks` | `pages/AgentEngPage.tsx` |
| `agenteng tools --discipline memory` | `pages/AgentEngPage.tsx` |
| `agenteng connect a2a` | `pages/AgentEngPage.tsx` |
| `agenteng connect mcp --transport http` | `pages/AgentEngPage.tsx` |
| `agenteng connect acp` | `pages/AgentEngPage.tsx` |
| `agenteng --info` | `pages/AgentEngPage.tsx` |

`agenteng guide --london` is shown as text on the /london-2026/guide page header, and `agenteng talks` and `agenteng event --london` on /talks and /london-2026, so they are listed by hand: the literal scanner only reads string literals, and skips literals that end like a sentence (such as the /agenteng meta description). `components/TicketsSection.tsx` still contains `agenteng tickets --london`, but the homepage no longer renders that section; the command keeps working and now reports the site's fully booked wording. The exporter fails if the homepage renders `TicketsSection` again, so the registration status is reviewed before the next export.

Personal agenda, bookmark, proposal and inbox commands are unsupported. Agenda topic filtering reads published programme text and creates no personal state.

Run `python scripts/check-website-stability.py WEBSITE_REPO` to verify public session/source IDs survive agenda reordering and duplicate IDs are rejected before export.

## Agent-to-Agent (A2A) Talks

`scripts/export-website.mjs` reads `src/data/agentToAgent.ts` (session, title, YouTube ID, tag and duration) and the page copy in `src/pages/AgentToAgent.tsx` (title, intro and the exact disclaimer) into `a2a_talks` in the catalogue, with one `a2a-talks` source. The export fails if the data shape changes. These AI-generated videos are never exported as speakers or sessions; the talks gallery keeps them as `kind: a2a` rows marked AI-generated, which `agenteng talks` lists only with `--a2a`, last, and general search and chat leave them out unless the question names A2A or Agent-to-Agent.

## Site structure (London 2026 archive, talks, /agenteng)

The site moved the London 2026 conference under `/london-2026`. Catalogue sources and answers use the new URLs:

| Old URL | New URL |
| --- | --- |
| `/speakers` | `/london-2026/speakers` (speaker anchors `#<slug>`) |
| `/agenda` | `/london-2026/agenda` |
| `/guide` | `/london-2026/guide` |
| `/#venue`, `/#agenda`, `/#tickets` | `/london-2026` |
| `/#faq` (London FAQ) | `/london-2026#faq` |
| `/#program` (tracks) | `/london-2026#tracks` |

The homepage still has `#faq` and `#truly-yours`; the old paths redirect on the site. New pages: `/london-2026` and its subpages, `/talks`, `/talks/:slug` and `/agenteng` (the CLI page; its commands are in the table above).

Data files read by `scripts/export-website.mjs`:

- `src/data/talks.ts`: the talks gallery, exported as `talks` (slug, title, kind, city, event, speaker, topics, `youtube_id`, `transcript`, status, AI-generated flag and `/talks/<slug>` URL, one `talk` source each). `talks.ts` builds its rows from other data, so the exporter rebuilds them from the same literals (agenda, speakers, `sf-code-engineering.ts`, the SF recordings literal and `agentToAgent.ts`) and fails if the mapping in `talks.ts` changes or if London or Code Engineering talks start publishing a YouTube ID or transcript, so a newly published recording is mirrored deliberately. No transcripts are published today, so none are exported.
- `src/data/sf-code-engineering.ts`: roles, companies and links for the Code Engineering San Francisco (27 October 2026) speakers, checked against the SanFrancisco page roster.
- `src/data/events.ts`: next and previous editions (`site_links.next_event` is Agent Engineering San Francisco, April 2027, `/san-francisco`; `site_links.previous_event` is London 2026, `/london-2026`), plus each event's `page_url`. The April 2027 conference is announced without a date or venue, so it is a link, not a catalogue event.
- `src/data/disciplines.ts`: the site now lists 14 disciplines. Factory Engineering and Decision Engineering are exported as `disciplines` and shown by `agenteng disciplines` as on the conference site with no tool listings yet; the tool directory keeps its twelve listed disciplines until tools are attributed to the new two.

Run `python scripts/check-website-commands.py WEBSITE_REPO` after each sync.
