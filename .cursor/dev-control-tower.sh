#!/usr/bin/env bash
# Launch the AUMARA Control Tower dev server for Cloud Agents.
# Runs in the zero-send "audit" stage. No live mail transport is loaded and no
# real secrets are used: the webhook token is an ephemeral, locally generated
# value so audit-mode authorization is exercised without a production secret.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../aumara-control-tower"

export AUMARA_ENV="${AUMARA_ENV:-cloud-agent}"
export AUMARA_AUTOMATION_MODE="${AUMARA_AUTOMATION_MODE:-audit}"
export PORT="${PORT:-8787}"

if [ -z "${AUMARA_WEBHOOK_TOKEN:-}" ]; then
  AUMARA_WEBHOOK_TOKEN="$(node -e 'process.stdout.write(require("crypto").randomBytes(24).toString("hex"))')"
  export AUMARA_WEBHOOK_TOKEN
fi

exec npm start
