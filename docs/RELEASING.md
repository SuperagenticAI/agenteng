# Releases

Release artifacts should contain only public source, documentation, event data and tool-directory metadata. Keep credentials, private notes, proposals, local environments and generated files out of Git. The installer source is versioned at `src/agenteng/data/install.sh`; generated release files live under ignored `dist/`.

Before a release:

```sh
uv sync --frozen --all-extras
uv run --frozen python scripts/check-public-release.py
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
uv run --frozen pytest -q
uv build
uv run --frozen python scripts/check-public-release.py --artifacts
uv run --frozen python scripts/verify-release.py
uv run --frozen python scripts/stage-release.py
```

Keep `pyproject.toml`, `agenteng.__version__`, the changelog and installer `VERSION`/default release URL consistent. Test a build from the source archive so an ignored local file cannot be a hidden dependency. CI checks Python 3.12 and 3.13; remote CI and Linux container results must be assessed before publication.

The archive uses an explicit file allowlist, and the release check inspects both Git candidates and packaged files. Neither `.gitignore` nor a pattern scan can guarantee the absence of secrets; review the final diff and artifact contents as well. If a real secret was committed or published, removing the file does not revoke it: rotate the credential and address the exposed history.

Publish the versioned wheel and `SHA256SUMS` together, then publish the installer on the official website. Checksums identify the released bytes but are not independent signatures. The installer must not point at a missing or unverified release. Package registry publication is a separate maintainer action; do not claim that `agenteng-hq` is on PyPI before it is available.

Staging also creates `agenteng-agent-guide.txt`, `agenteng-events.json` and `agenteng-tools.json` for the website. The feed is a dated snapshot, not live availability. Publish and link the guide only after verifying the referenced agent host; add its link to the website's existing `llms.txt` without replacing that file's established event/organizer facts. Rebuild the feeds whenever the public event catalogue or tool directory changes. No staging command edits or deploys the website.

The intended GitHub repository is `SuperagenticAI/agenteng`; package and documentation links use that address. For GitHub publication, enable private vulnerability reporting, set branch protection requiring CI and review, and give release credentials only to approved maintainer workflows. Avoid workflows that execute untrusted pull-request code with write credentials. The provided CI workflow has read-only repository permissions and no deployment steps.

See [deployment](../deploy/README.md) for hosting configuration and post-deployment checks. This document does not promise a release schedule or maintenance SLA.
