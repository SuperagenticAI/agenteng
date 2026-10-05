# 📦 Releases and documentation

Release artifacts should contain only public source, documentation, event data and tool-directory metadata. Keep credentials, private notes, proposals, local environments and generated files out of Git. The installer source is versioned at `src/agenteng/data/install.sh`; generated release files live under ignored `dist/`.

## Tag-triggered PyPI publishing

`.github/workflows/publish.yml` follows the SuperQode release pattern: pushing a
`v*` version tag runs the reusable CI workflow, publishes the verified wheel and
source archive to PyPI, and creates or updates the matching GitHub release with
those files and `SHA256SUMS`. Publishing waits for both Python 3.12 and 3.13 jobs,
including the full test suite, lint/format, archive audit and core-only wheel check.
The credentialed job downloads the already-tested Python 3.12 artifacts instead
of rebuilding them.

One-time setup: in the `SuperagenticAI/agenteng` repository's **Settings → Secrets
and variables → Actions**, add `PYPI_API_TOKEN` containing a PyPI API token
that can publish `agenteng`. The workflow maps it to `UV_PUBLISH_TOKEN`, matching
SuperQode's setup. An organization secret can also be used if this repository is
authorized to access it. A token scoped only to `superqode` cannot publish another
project. Never put the token in source, logs or an issue. This workflow uses token
authentication, not PyPI Trusted Publishing/OIDC.

Before tagging, update `pyproject.toml`, `src/agenteng/__init__.py`, the project
version in `uv.lock`, installer `VERSION` and its default versioned release URL.
Update the changelog and release-facing documentation. Check locally:

```sh
uv run --frozen python scripts/check-release-metadata.py --tag v0.0.2
```

Commit and push the workflow and version changes first. Then tag the intended
commit and push that tag:

```sh
git tag -a v0.0.2 -m 'AgentEng 0.0.2'
git push origin v0.0.2
```

The tag must exactly match `v` plus the package version. Canonical tags such as
`v0.2.0rc1` work when all version files match; prerelease/dev tags produce a GitHub
prerelease. Normal branch pushes and pull requests run CI without publishing.
Forks do not publish through this workflow.

For a retry, use **Actions → Publish → Run workflow**, supplying the existing
tag. The tag is resolved to an immutable commit before verification and rechecked
before publishing. `uv publish --check-url` checks distributions already on PyPI,
allowing a partially completed release to be retried; it does not overwrite a
published version. Do not move an already-published tag. Use a new version for
changed release bytes.

The PyPI workflow does not deploy the server or publish website assets. A separate
Cloud Build GitHub trigger can deploy Cloud Run from the same version tag using
`cloudbuild.yaml`. Configure **Push new tag**, regex `^v.*$` and that YAML
file, following the [console setup guide](https://github.com/SuperagenticAI/agenteng/blob/main/deploy/README.md).
Complete its repository connection, registry and service-account setup before
tagging. Cloud Build validates/tests the source and checks the live MCP/A2A service;
its result is independent of the PyPI Publish workflow. Ordinary commits do not
invoke this deployment trigger.

The staged
installer, wheel, checksum and discovery feeds remain a separate website release.
PyPI availability should only be announced after the Publish run succeeds. See
[uv publishing documentation](https://docs.astral.sh/uv/guides/package/).

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

Publish the versioned wheel and `SHA256SUMS` together, then publish the installer on the official website. Checksums identify the released bytes but are not independent signatures. The installer must not point at a missing or unverified release. Package registry publication is a separate maintainer action; do not claim that `agenteng` is on PyPI before it is available.

Staging also creates `agenteng-agent-guide.txt`, `agenteng-events.json` and `agenteng-tools.json` for the website. The feed is a dated snapshot, not live availability. Publish and link the guide only after verifying the referenced agent host; add its link to the website's existing `llms.txt` without replacing that file's established event/organizer facts. Rebuild the feeds whenever the public event catalogue or tool directory changes. No staging command edits or deploys the website.

The intended GitHub repository is `SuperagenticAI/agenteng`; package and documentation links use that address. For GitHub publication, enable private vulnerability reporting, set branch protection requiring CI and review, and give release credentials only to approved maintainer workflows. Avoid workflows that execute untrusted pull-request code with write credentials. The provided CI workflow has read-only repository permissions and no deployment steps.

See [deployment](https://github.com/SuperagenticAI/agenteng/blob/main/deploy/README.md) for hosting configuration and post-deployment checks. This document does not promise a release schedule or maintenance SLA.

## Documentation on GitHub Pages

Public documentation is written in Markdown under `docs/` and built with MkDocs
Material, using the event website's logo and favicon. The intended site URL is
`https://superagenticai.github.io/agenteng/`. Preview and verify it locally:

```sh
uv venv .venv-docs --python 3.12
uv pip install --python .venv-docs/bin/python -r requirements-docs.txt
.venv-docs/bin/python -m mkdocs serve
.venv-docs/bin/python -m mkdocs build --strict
```

In the repository's **Settings → Pages → Build and deployment**, select
**GitHub Actions** as the source. After the changes are pushed to `main`, the
Documentation workflow builds and publishes the site. Pull requests build it
without deploying; **Actions → Documentation → Run workflow** on `main` can retry
publication. No separate publishing token or `gh-pages` branch is required.
See [GitHub's Pages workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

Keep the site small: update the existing guides and quick start before adding
pages. `mkdocs.yml` explicitly includes reviewed public documents and brand assets.
Add any new public page to both the include list and navigation. Generated
`site/` and the documentation environment are ignored; do not commit them.
