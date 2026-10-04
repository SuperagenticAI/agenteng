The container can host the public catalogue, MCP and A2A service on Cloud Run. Select your Google Cloud project and HTTPS origin before deployment. The official public service is not yet published.

```sh
# Requires authenticated gcloud, billing and Cloud Build/Run/Artifact Registry APIs.
# Use a unique release tag for each rebuild.
gcloud builds submit --project YOUR_PROJECT --config deploy/cloudbuild.yaml \
  --substitutions=_REGION=europe-west1,_TAG=v0.1.0
```

The Artifact Registry `cloud-run-source-deploy` repository must exist in the selected region. The build account needs repository writer, Cloud Run deploy permissions and service account user on the runtime identity. Use a dedicated runtime service account with no data-store or model credentials for this public lookup service.

Map `a2a.agentengineering.world` to the service using the project's supported HTTPS domain/load-balancer setup. The application checks this Host header, plus loopback hosts; an unconfigured `run.app` hostname is intentionally rejected. To test using the generated Cloud Run URL, temporarily set `AGENTENG_PUBLIC_URL` to that URL, then restore the custom domain before discovery verification.

```sh
uv run --frozen --extra server python scripts/check-hosted.py https://a2a.agentengineering.world
```

Routes: A2A JSON-RPC `/` with `A2A-Version: 1.0`, discovery `/.well-known/agent-card.json`, MCP `/mcp/`, HTTP `/v1/query`, `/health`, `/catalogue.json` and `/install.sh`. The trailing slash on the MCP URL avoids a redirect. No streaming/push A2A capability is advertised. Public lookup has zero model calls; compute, HTTPS hosting and network traffic still have their usual hosting costs.

GET `/` and `/events/EVENT_ID` serve crawlable public pages. `/events.json`, `/llms.txt`, `/robots.txt` and `/sitemap.xml` support event discovery. The source catalogue covers London and San Francisco only. See [coding-agent setup](../docs/INTEGRATIONS.md).

This deployment keeps `AGENTENG_ENABLE_INTAKE=0`. Offline drafts can be prepared through the public service, but it creates no private inbox. Do not enable the SQLite pilot on Cloud Run's ephemeral filesystem. A private intake deployment needs persistent encrypted storage, participant credentials, a privacy/retention policy and organizer administration; see [participation](../docs/PARTICIPATION.md).

The process limit is 300 POST/DELETE requests per minute. For quotas across replicas or per caller, use the HTTPS gateway/load balancer. Both inference flags remain off in this public image. Optional inference requires a separate operator configuration with the extra installed, a provider and bearer credential. Per-request limits do not impose a daily monetary budget across replicas; keep it operator-only and configure provider/project spending limits before enabling it.

Publish the installer on the main website after building and staging the release:

```sh
uv build
uv run python scripts/stage-release.py
# Copy dist/website-public contents into the website's public/ directory and publish it.
```

That publishes `/install.sh`, `/releases/0.1.0/agenteng-0.1.0-py3-none-any.whl` and its `SHA256SUMS`. Integrate the staged files into your website deployment pipeline. The service also serves the same installer, which downloads its versioned release from the main website. Test the three public URLs before announcing installation. The script uses HTTPS and verifies the wheel checksum before creating a user-owned Python environment; it needs Python 3.12+, curl, venv and pip. It refuses to replace an unrelated `agenteng` executable.

Refresh `catalogue.json` from the website sources and rebuild whenever public event content changes. The exporter fails on known inline/calendar metadata drift, rather than silently reusing it. The API reports the source commit/hash, export time and staleness. Catalogue refresh is a build-time action; there is no polling job or private database connection in this release.

Reference documentation: [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/), [Cloud Run deployment](https://docs.cloud.google.com/run/docs/deploying-source-code), [Cloud Run custom domains](https://docs.cloud.google.com/run/docs/mapping-custom-domains).
