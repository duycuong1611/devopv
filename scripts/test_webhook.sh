#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
ENV_FILE="${ENV_FILE:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Run: cp .env.example .env" >&2
  exit 1
fi

SECRET="$(grep '^GITHUB_WEBHOOK_SECRET=' "$ENV_FILE" | cut -d= -f2-)"
if [[ -z "$SECRET" || "$SECRET" == "replace_with_a_long_random_secret" ]]; then
  echo "Set GITHUB_WEBHOOK_SECRET in $ENV_FILE first." >&2
  exit 1
fi

DELIVERY_ID="local-$(date +%s)"
BODY='{"ref":"refs/heads/main","repository":{"full_name":"local/relayops"},"sender":{"login":"local-user"}}'
SIGNATURE="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | sed 's/^.* //')"

curl --fail-with-body -i -X POST "$BASE_URL/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: $DELIVERY_ID" \
  --data "$BODY"
