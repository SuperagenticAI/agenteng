#!/usr/bin/env bash
# Called by Cloud Build after release validation, tests and image publication.
set -euo pipefail

: "${DEPLOY_PROJECT:?Set DEPLOY_PROJECT}"
: "${DEPLOY_REGION:?Set DEPLOY_REGION}"
: "${DEPLOY_SERVICE:?Set DEPLOY_SERVICE}"
: "${DEPLOY_IMAGE:?Set DEPLOY_IMAGE}"
: "${DEPLOY_RUNTIME_ACCOUNT:?Set DEPLOY_RUNTIME_ACCOUNT}"

public_url="${DEPLOY_PUBLIC_URL:-}"
public_url="${public_url%/}"
if [ -n "$public_url" ] && [[ ! "$public_url" =~ ^https://[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ ]]; then
  echo 'DEPLOY_PUBLIC_URL must be an HTTPS origin without a path, credentials or port.' >&2
  exit 1
fi

if [ -z "$public_url" ]; then
  public_url=$(gcloud run services describe "$DEPLOY_SERVICE" \
    --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" \
    --format='value(status.url)' 2>/dev/null || true)
fi
# A service's generated URL is only available after its first creation. Keep
# strict host validation during bootstrap, then replace this origin below.
public_url="${public_url:-https://a2a.agentengineering.world}"

gcloud run deploy "$DEPLOY_SERVICE" \
  --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" \
  --image="$DEPLOY_IMAGE" --service-account="$DEPLOY_RUNTIME_ACCOUNT" \
  --no-invoker-iam-check --ingress=all --port=8080 \
  --min-instances=0 --max-instances=2 --concurrency=40 \
  --memory=512Mi --cpu=1 --cpu-throttling --timeout=60 --quiet \
  --update-env-vars="AGENTENG_PUBLIC_URL=$public_url,AGENTENG_ALLOWED_ORIGINS=https://agentengineering.world"

if [ -z "${DEPLOY_PUBLIC_URL:-}" ]; then
  generated_url=$(gcloud run services describe "$DEPLOY_SERVICE" \
    --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" \
    --format='value(status.url)')
  if [ -z "$generated_url" ]; then
    echo 'Cloud Run did not return a service URL.' >&2
    exit 1
  fi
  if [ "$public_url" != "$generated_url" ]; then
    gcloud run services update "$DEPLOY_SERVICE" \
      --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" --quiet \
      --update-env-vars="AGENTENG_PUBLIC_URL=$generated_url"
  fi
  public_url="$generated_url"
fi

# Restore release traffic even if an earlier UI deployment pinned a revision.
gcloud run services update-traffic "$DEPLOY_SERVICE" \
  --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" --to-latest --quiet

url_file="${DEPLOY_URL_FILE:-.cache/cloud-run-url}"
mkdir -p "$(dirname "$url_file")"
printf '%s\n' "$public_url" > "$url_file"
printf 'AgentEng deployed at %s\n' "$public_url"
