#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
npm --prefix apps/web ci --strict-ssl=true
