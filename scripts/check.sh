#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check apps/api
(cd apps/api && ../../.venv/bin/pytest)
(cd apps/web && npm run lint && npm run typecheck && npm run build)
docker compose config --quiet
