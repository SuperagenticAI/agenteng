# Cloud Run deployment through the Google Cloud UI

The repository contains the container, release checks and deployment pipeline for
the public catalogue, MCP and A2A service. The official public service is live at
`https://a2a.agentengineering.world`. Complete the setup below in the Google Cloud
console; no local `gcloud` installation or Google Cloud key in GitHub is required.

A new matching version tag starts two independent pipelines: Cloud Build deploys
the service, and GitHub Actions publishes `agenteng` to PyPI. Ordinary commits
run GitHub CI and documentation publishing, without deploying Cloud Run or PyPI.
Both release pipelines validate the tag against the package version and test the
source before publication.

## 1. Push the deployment files

Commit and push the reviewed changes to `SuperagenticAI/agenteng` before creating
a release tag. The tagged commit must contain `Dockerfile`, `uv.lock`,
`cloudbuild.yaml`, `deploy/deploy-cloud-run.sh`, `src/`, `scripts/` and
`tests/`. Do not tag an older commit that lacks this configuration.

## 2. Prepare the Google Cloud project

Select the project at the top of the console and ensure billing is enabled.
In **APIs & Services → Library**, enable Cloud Build, Cloud Run, Artifact Registry,
Cloud Resource Manager, Identity and Access Management (IAM), and Secret Manager
APIs. The GitHub connection stores its managed connection credentials in Secret
Manager; see [Google's GitHub connection guide](https://docs.cloud.google.com/build/docs/automating-builds/github/connect-repo-github?generation=2nd-gen).

In **Artifact Registry → Repositories → Create repository**, choose:

| Setting | Value |
| --- | --- |
| Name | `cloud-run-source-deploy` |
| Format | Docker |
| Location type | Region |
| Region | `europe-west1` |

Use the same project and region throughout this guide. The repository holds
version-tagged container images, separate from the Python files on PyPI.

## 3. Create the build and runtime identities

In **IAM & Admin → Service Accounts → Create service account**, create
`agenteng-runtime`. Leave the project-role and user-access steps empty. The
public runtime reads its bundled catalogue and needs no model or database roles.

Create a second account, `agenteng-build`, with these project roles:

| Console role | Role ID | Purpose |
| --- | --- | --- |
| Cloud Build Legacy Service Account | `roles/cloudbuild.builds.builder` | Build execution, source/artifact access and logs |
| Cloud Run Admin | `roles/run.admin` | Create/update the service, public access and release traffic |

The first role's name refers to its predefined permission bundle; select it for
the dedicated build account. It is different from **Cloud Build Service Agent**,
which belongs to Google's managed service identity. The build-role permissions
are documented in [Google's Cloud Build account reference](https://docs.cloud.google.com/build/docs/cloud-build-service-account).

Open **agenteng-runtime → Permissions → Grant access**. Add
`agenteng-build@YOUR_PROJECT_ID.iam.gserviceaccount.com` with **Service Account
User** (`roles/iam.serviceAccountUser`) on this runtime account. This allows the
builder to deploy a revision using that identity. Use your actual project ID in
the address. No downloaded service-account keys are needed.

The person configuring the trigger also needs permission to use `agenteng-build`
and manage Cloud Build triggers. If the account is unavailable in the trigger's
selector, check the user's `iam.serviceAccounts.actAs` permission. See
[user-managed build accounts](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts).

## 4. Connect GitHub and create a tag trigger

Open **Cloud Build → Repositories**, select **2nd gen** and `europe-west1`, then
create a GitHub connection. Authorize the Google Cloud Build GitHub app for
`SuperagenticAI/agenteng` and link that repository. Organization authorization
may require a GitHub organization owner. Use the console's prompts for the
managed connection credentials.

Open **Cloud Build → Triggers → Create trigger** and enter:

| Setting | Value |
| --- | --- |
| Name | `agenteng-release` |
| Region | `europe-west1` |
| Event | **Push new tag** |
| Source | Connected 2nd-generation GitHub repository |
| Repository | `SuperagenticAI/agenteng` |
| Tag regex | `^v.*$` |
| Configuration type | **Cloud Build configuration file (yaml or json)** |
| Configuration location | Repository |
| Configuration file path | `cloudbuild.yaml` |
| Service account | `agenteng-build@YOUR_PROJECT_ID.iam.gserviceaccount.com` |
| Included / ignored files | Leave both empty |

The root file layout follows [SuperQode's Cloud Build setup](https://github.com/SuperagenticAI/superqode/blob/main/cloudbuild.yaml):
`cloudbuild.yaml` defines the build/deploy pipeline, and `Dockerfile` defines the
container. Choose the **Cloud Build configuration file** option for this trigger.
The YAML invokes `docker build -f Dockerfile .`, using the repository root as its
build context. If a UI asks for the Dockerfile path, it is `Dockerfile`; the
directory/context is `.`. Keep `CLOUD_LOGGING_ONLY` in the YAML for the
user-managed build account.

The verification step installs Git because `python:3.12-slim` omits it and the
release tests check Git ignore rules. It trusts only the shared `/workspace`
checkout for Git ownership checks. Git is not added to the runtime container.

Keep the repository connection and trigger regions identical. Select the YAML
configuration: it performs validation, tests, image publication, deployment and
live endpoint checks. The Cloud Run repository wizard's default branch trigger
(named like `rmgpgab-agenteng-europe-west1-...`) does not implement this release
policy and redeploys on every push to `main`. Disable it so only the
`push-new-tag` trigger deploys the service.
See [Google's trigger setup guide](https://docs.cloud.google.com/build/docs/automating-builds/create-manage-triggers).

### Disable the per-commit Cloud Run branch trigger

GitHub Actions never deploys Cloud Run for this repository, and PyPI publishing
is tag-only (`.github/workflows/publish.yml`). The Cloud Build triggers live in
Google Cloud, not in this repository, so changing them needs console or `gcloud`
access. They show up as GitHub check runs:

| Check run name | When it runs | Keep? |
| --- | --- | --- |
| `push-new-tag (agenteng-510707)` | New `v*` tags | Yes (release deploy) |
| `rmgpgab-agenteng-europe-west1-SuperagenticAI-agenteng--mappc (agenteng-510707)` | Every push to `main` | No (wizard branch trigger) |

**Console**

1. Open [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers?project=agenteng-510707) in `europe-west1`.
2. Find the branch trigger whose check name starts with `rmgpgab-agenteng-`
   (created by the Cloud Run source deploy wizard for branch `main`).
3. **Disable** (or delete) it.
4. Confirm the release trigger remains: event **Push new tag**, tag regex
   `^v.*$`, config `cloudbuild.yaml`.
5. On the release trigger, make sure `_PUBLIC_URL` is not overridden with an
   empty value, so the `cloudbuild.yaml` default (`https://a2a.agentengineering.world`)
   applies. See [Custom domain and operation](#custom-domain-and-operation).

**gcloud** (after `gcloud auth login`):

```bash
# List triggers and find the branch (main) trigger name
gcloud builds triggers list --region=europe-west1 --project=agenteng-510707

# Disable it: export, set `disabled: true`, then import
gcloud builds triggers export NAME --region=europe-west1 \
  --project=agenteng-510707 --destination=trigger.yaml
# edit trigger.yaml and add: disabled: true
gcloud builds triggers import --region=europe-west1 \
  --project=agenteng-510707 --source=trigger.yaml
```

After the branch trigger is disabled, an ordinary push to `main` must not create
a Google Cloud Build check run; only a new `v*` tag should start
`push-new-tag` with `cloudbuild.yaml`.

The YAML already supplies these defaults. You only need substitutions if you
change the names or region:

| Substitution | Default |
| --- | --- |
| `_REGION` | `europe-west1` |
| `_SERVICE` | `agenteng` |
| `_REPOSITORY` | `cloud-run-source-deploy` |
| `_RUNTIME_ACCOUNT` | `agenteng-runtime` (account ID, not its full email) |
| `_PUBLIC_URL` | `https://a2a.agentengineering.world`; set it empty to use the generated `run.app` URL, or to another HTTPS origin |

For the already-published `v0.0.1` tag, add `_SERVICE=agenteng` in the trigger's
substitution variables. That tag originally defaults to `agenteng-hq`; the trigger
override selects `agenteng` without changing the immutable published source.
The current source defaults to `agenteng` for future releases.

There is no `_TAG` setting. Cloud Build supplies `TAG_NAME` from the GitHub tag
event. Missing or mismatched tags fail the release check before image deployment.

## 5. Configure PyPI and publish the first tag

In GitHub **Settings → Secrets and variables → Actions**, add `PYPI_API_TOKEN`
with permission to publish the `agenteng` project. See the
[release guide](../docs/RELEASING.md) for token setup and version updates.

After all the setup above and the source changes are pushed, open GitHub
**Releases → Draft a new release → Choose a tag**. Create `v0.0.1`, targeting the
reviewed `main` commit, and publish the release. This is the version currently
declared in the source. If that version already exists on PyPI, use a new version
and update all release metadata before creating its matching tag.
See [GitHub's release instructions](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

Watch **GitHub → Actions → Publish** for PyPI and **Cloud Build → History** for the
container deployment. They run independently; one succeeding does not imply the
other succeeded. Publish one release at a time so an older in-flight deployment
cannot finish after a newer one. Existing tags do not automatically fire a newly
created trigger; use the trigger's **Run** action with the existing release tag
when deploying an already-published release.

## 6. Verify the service

Cloud Build creates **Cloud Run → Services → agenteng** automatically. The
deployment sets the runtime account, public access, port `8080`, one CPU, 512 MiB
memory, zero minimum instances, two maximum instances per revision, concurrency
40 and a 60-second request timeout. It directs service traffic to the latest
revision and keeps ordinary synthesis, RLM and private intake disabled.

On the first deployment, a second revision sets `AGENTENG_PUBLIC_URL` to Google's
generated HTTPS URL. Later releases reuse that URL. This preserves strict Host
validation while making the default Cloud Run URL usable without manual edits.
The final build step checks health, discovery pages, a real A2A query and MCP
initialization/tool invocation. The build succeeds only when those checks pass.

Click the service URL and inspect `/health` and `/.well-known/agent-card.json`.
Use `<SERVICE_URL>/mcp/` for remote MCP clients; retain its trailing slash.

If a build fails, open its failed step in **Cloud Build → History**:

| Failed step | Check |
| --- | --- |
| `verify-release` | Tag/version agreement, dependency installation, lint or tests |
| `push-image` | Registry name/region and build account permissions |
| `deploy-service` | Runtime account exists, Service Account User grant, Cloud Run permissions |
| `check-hosted-service` | Service URL, public access, custom-domain routing and application logs |

A smoke-check failure happens after deployment and does not automatically roll
back traffic. Inspect the service before announcing the release. Correct console
configuration and rerun the same immutable tag, or release a new version for code
changes. Never move a published tag or overwrite published package bytes.

## Custom domain and operation

Production traffic for `https://a2a.agentengineering.world` is live, and
`cloudbuild.yaml` now uses it as the default `_PUBLIC_URL`. Tag deploys keep
advertising that origin without any trigger substitution. Keep HTTPS routing and
its certificate in place.

Forks and other deployments override `_PUBLIC_URL` on their own trigger: set it
to an empty value to fall back to the generated `run.app` URL (the deploy script
then reads the service URL), or to another HTTPS origin once its routing and
certificate are ready. A trigger substitution always wins over the YAML default.

Only the `push-new-tag` trigger should deploy. Disable the wizard branch trigger
(`rmgpgab-...`) so pushes to `main` do not redeploy the service. Google's built-in Cloud Run domain mapping is currently a preview
feature and is not recommended for production; use its documented production
hosting options, such as an external Application Load Balancer with a serverless
backend. See
[Cloud Run custom domains](https://docs.cloud.google.com/run/docs/mapping-custom-domains).
The app trusts the configured hostname and loopback hosts; it does not trust
every `run.app` hostname. Do not clear `_PUBLIC_URL` on the production trigger
unless you intend to fall back to the generated URL.

For an additional manual check from an environment with the server dependencies:

```sh
uv run --frozen --extra server python scripts/check-hosted.py https://a2a.agentengineering.world
```

### Troubleshooting: Invalid host header

A `400` response with `Invalid host header` means `AGENTENG_PUBLIC_URL` does not
match the request `Host`. The usual cause is a deploy that ran with an empty
`_PUBLIC_URL` (an older `cloudbuild.yaml` default, an explicit empty trigger
substitution, or the wizard branch trigger), which resets `AGENTENG_PUBLIC_URL`
to the generated `run.app` URL.

To fix it: make sure the trigger has no empty `_PUBLIC_URL` override (the YAML
default is now `https://a2a.agentengineering.world`), disable the wizard branch
trigger so only `push-new-tag` deploys, and rerun the release tag from a source
that includes this default. As an immediate fix, set the Cloud Run environment
variable `AGENTENG_PUBLIC_URL` to `https://a2a.agentengineering.world`. Then verify with the `check-hosted.py` command above. You
should see HTTP 200 on `/health` and `/.well-known/agent-card.json`.

Routes: A2A JSON-RPC `/` with `A2A-Version: 1.0`, discovery `/.well-known/agent-card.json`, MCP `/mcp/`, HTTP `/v1/query`, `/health`, `/catalogue.json` and `/install.sh`. The trailing slash on the MCP URL avoids a redirect. No streaming/push A2A capability is advertised. Public lookup has zero model calls; compute, HTTPS hosting and network traffic still have their usual hosting costs.

GET `/` and `/events/EVENT_ID` serve crawlable public pages. `/events.json`, `/llms.txt`, `/robots.txt` and `/sitemap.xml` support event discovery. The source catalogue covers London and San Francisco only. See [coding-agent setup](../docs/INTEGRATIONS.md).

This deployment keeps `AGENTENG_ENABLE_INTAKE=0`. Offline drafts can be prepared through the public service, but it creates no private inbox. Do not enable the SQLite pilot on Cloud Run's ephemeral filesystem. A private intake deployment needs persistent encrypted storage, participant credentials, a privacy/retention policy and organizer administration; see [participation](../docs/PARTICIPATION.md).

The process limit is 300 POST/DELETE requests per minute. For quotas across replicas or per caller, use the HTTPS gateway/load balancer. Both inference flags remain off in this public image. Optional inference requires a separate operator configuration with the extra installed, a provider and bearer credential. Per-request limits do not impose a daily monetary budget across replicas; keep it operator-only and configure provider/project spending limits before enabling it.

Publish the installer on the main website after staging the release:

```sh
uv run python scripts/stage-release.py
# Copy dist/website-public/install.sh (plus the staged guide and feeds) into
# the website public/ directory and publish it.
```

That stages `/install.sh` plus discovery feeds. A website wheel mirror is not
required: the installer installs the latest AgentEng from PyPI via `uv tool install`
(with a pip virtualenv fallback). The Cloud Run service also serves the same
script at `/install.sh` as a mirror. The advertised URL is
`https://agentengineering.world/install.sh`, served from `public/install.sh` in
agent-engineering-summit; re-sync that copy after every installer change. The
GoDaddy host shows a bot-check page to cloud and datacenter IPs, so verify the
main-site copy from a normal network with `curl -fsSL <url> | head -1` (expect
`#!/bin/sh`) before announcing installation. The installer needs a POSIX shell and network access; it bootstraps
uv when missing and never uses sudo.

Refresh `catalogue.json` from the website sources and rebuild whenever public event content changes. The exporter fails on known inline/calendar metadata drift, rather than silently reusing it. The API reports the source commit/hash, export time and staleness. Catalogue refresh is a build-time action; there is no polling job or private database connection in this release.

Reference documentation: [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/), [Cloud Run deployment](https://docs.cloud.google.com/run/docs/deploying-source-code), [Cloud Run custom domains](https://docs.cloud.google.com/run/docs/mapping-custom-domains).
