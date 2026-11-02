#!/usr/bin/env bash
# Offline checks: no AWS credentials needed, no Docker.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-dev.txt
fi

echo "==> Contact flow JSON parses"
.venv/bin/python -c "import json; json.load(open('connect/flows/inbound-flow.json')); print('ok')"

echo "==> Lambda compiles"
python3 -m py_compile lambda/fulfillment/handler.py && echo ok

echo "==> Render template"
.venv/bin/python scripts/render_template.py build/template.yaml

echo "==> cfn-lint (source and rendered template, ap-southeast-1)"
.venv/bin/cfn-lint --regions ap-southeast-1 -- infra/template.yaml build/template.yaml && echo ok

echo "==> Shell scripts parse"
for f in scripts/deploy.sh scripts/teardown.sh scripts/verify.sh; do bash -n "$f"; done && echo ok

echo "==> Unit tests"
.venv/bin/python -m pytest -q
