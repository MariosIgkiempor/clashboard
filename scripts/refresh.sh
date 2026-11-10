#!/usr/bin/env bash
# Force a refresh now: pull transcripts from the MacBook, then run the Dagster full_refresh job
# (bronze -> silver -> dbt -> gold -> parquet export). Run on hefty; the stack must be up (it shares
# the Dagster instance in .dagster_home, so the run also shows in the UI).
#   scripts/refresh.sh            pull + rebuild
#   scripts/refresh.sh --no-pull  rebuild only
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a
export CLASHBOARD_DATA_DIR="$ROOT/data" DAGSTER_HOME="$ROOT/.dagster_home"
[[ "${1:-}" == "--no-pull" ]] || scripts/pull_from_macbook.sh
cd orchestration && uv run dg launch --job full_refresh
