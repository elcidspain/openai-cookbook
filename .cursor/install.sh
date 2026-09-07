#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the OpenAI Cookbook fork.
# Prepares the Python cookbook tooling and the Node control-tower service.
set -euo pipefail

# Resolve the repository root (the directory that contains this .cursor folder).
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# The default base image ships Python 3.12 and Node 22 but omits the stdlib
# venv/ensurepip module. Install it once (idempotent) so .venv can be created.
if ! python3 -m ensurepip --version >/dev/null 2>&1; then
  echo "==> System: installing python3-venv (ensurepip)"
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12-venv
fi

echo "==> Python: create/refresh virtual environment (.venv)"
if ! ./.venv/bin/python -m pip --version >/dev/null 2>&1; then
  rm -rf .venv
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install --upgrade pip

# Cookbook development tooling:
# - nbformat: required by .github/scripts/check_notebooks.py
# - PyYAML:   registry.yaml linting per AGENTS.md
# - jupyterlab: interactive notebook development (jupyter lab / notebook)
echo "==> Python: install cookbook tooling"
./.venv/bin/python -m pip install nbformat PyYAML jupyterlab

# Node control-tower service (transactional email/webhook + daily-ops dashboard).
if [ -f "aumara-control-tower/package.json" ]; then
  echo "==> Node: install aumara-control-tower dependencies"
  if [ -f "aumara-control-tower/package-lock.json" ]; then
    (cd aumara-control-tower && npm ci --no-audit --no-fund)
  else
    (cd aumara-control-tower && npm install --no-audit --no-fund)
  fi
fi

echo "==> Install complete"
