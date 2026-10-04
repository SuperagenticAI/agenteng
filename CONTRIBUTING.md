# Contributing

AgentEng connects people and agents to public Agent Engineering HQ events. Contributions to the CLI, shared catalogue service, MCP/A2A adapters, accessibility and documentation are welcome.

Start by checking existing issues. Use the bug or feature issue form for software changes; use the public event discussion form for ideas you are comfortable sharing openly. Private speaker proposals and organizer enquiries belong in the channels in [Community participation](docs/COMMUNITY.md).

An issue, pull request or event idea is a request for consideration. Maintainers may ask for revisions, defer, decline or close it. There is no guaranteed response time, merge, event booking or follow-up. A software contribution does not create an obligation to organize an event.

## Development

Python 3.12+ and [uv](https://docs.astral.sh/uv/) are required. Fork or clone [SuperagenticAI/agenteng](https://github.com/SuperagenticAI/agenteng), then run:

```sh
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
```

Keep changes focused. Explain the user-visible behavior and the validation in your pull request. Add meaningful tests for behavior changes. Documentation-only changes do not need new tests. All normal tests use local fixtures or scripted providers, so they need no model keys or paid API calls.

Runtime code lives in `src/agenteng`. Public catalogue export is in `scripts/export-website.mjs`; it requires a checkout of the website with TypeScript installed. Most contributors can use the bundled catalogue without that checkout. Changes to event facts should cite the original public page; do not invent dates, prices or availability. Report content corrections privately to the organizer if you cannot update the source website.

## Contribution boundaries

- Keep lookup and `auto` free of server-side model calls. Optional inference stays disabled by default.
- Keep RLM at depth one with one shared child/leaf delegation allowance.
- Preserve source attribution, date precision, timezone handling and snapshot freshness.
- Never commit credentials, attendee/contact lists, submission drafts, private proposals or organizer notes. Store drafts under ignored `proposal-drafts/` or outside the checkout; an arbitrary export filename is not automatically protected by Git. `.env.example` is a public template with no real keys.
- Do not make paid API calls or external submissions in tests. Do not weaken credential, origin, host or sandbox limits to make a test pass.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities using [SECURITY.md](SECURITY.md).

## License

By submitting a code or documentation contribution for inclusion in this project, you agree to license it under Apache-2.0, unless you clearly identify a compatible third-party license. Keep existing notices and identify copied or generated third-party material. Event and speaker content has separate attribution considerations described in [DATA.md](docs/DATA.md).

## Tool-directory changes

Suggest new entries, corrected links, aliases, duplicate merges or discipline tags using primary public references. Disclose affiliations and avoid unsupported popularity, performance or licensing claims. See [directory data and refresh](docs/TOOLS.md). Maintainer review does not guarantee inclusion or a response deadline. Keep personal/private proposal material out of public tool reports.
