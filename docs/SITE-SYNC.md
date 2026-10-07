# Website command verification

Every displayed AgentEng command must be accepted by the CLI. The hero Orchestrator demonstrates `agenteng connect a2a`, `agenteng connect mcp --transport http`, and `agenteng connect acp`, then says “Welcome to AgentEng!”. These protocol commands print usable setup instructions; the animated website panels do not execute a shell or claim live connections.

Run `python scripts/check-website-commands.py WEBSITE_REPO` against a website checkout with Node dependencies installed. It reads public TypeScript literals using the AST, validates them against the actual CLI, and executes public lookup/setup commands. Server loops and coding sessions are parsed without launching them. Dynamic speaker-profile command rendering is covered by the speaker fixture and website tests.

The fixture contains 82 command locations. Tool CI executes each row and requires success. Update it when website commands change.

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
| `agenteng speaker sergey-ignatov` | `data/speaker-stack.ts` |
| `agenteng speaker jon-bratseth` | `data/speaker-stack.ts` |
| `agenteng speaker meryem-arik` | `data/speaker-stack.ts` |
| `agenteng speaker frederic-barthelet` | `data/speaker-stack.ts` |
| `agenteng speaker stas-bichenko` | `data/speaker-stack.ts` |
| `agenteng speaker jocelyn-darcy` | `data/speaker-stack.ts` |

Personal agenda, bookmark, proposal and inbox commands are unsupported. Agenda topic filtering reads published programme text and creates no personal state.

Run `python scripts/check-website-stability.py WEBSITE_REPO` to verify public session/source IDs survive agenda reordering and duplicate IDs are rejected before export.
