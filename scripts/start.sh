#!/usr/bin/env bash
# Start everything Clashboard needs: Azurite (docker), Dagster (runs dbt), Streamlit.
# Usage: scripts/start.sh [--bootstrap]
#   --bootstrap  also run the full pipeline once (containers, bronze sync, silver, dbt, gold export)
# Ctrl-C stops Dagster and Streamlit. Azurite is left running (docker stop azurite to stop it).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BOOTSTRAP=0
[[ "${1:-}" == "--bootstrap" ]] && BOOTSTRAP=1

die() { echo "ERROR: $*" >&2; exit 1; }

# --- prerequisites -----------------------------------------------------------
command -v uv >/dev/null || die "uv not installed (https://docs.astral.sh/uv/)"
command -v docker >/dev/null || die "docker not installed"
docker info >/dev/null 2>&1 || die "docker daemon not running; start Docker Desktop"
[[ -f .env ]] || die ".env missing (needs AZURE_STORAGE_CONNECTION_STRING, STORAGE_MODE, CLASHBOARD_DATA_DIR, DAGSTER_HOME)"

set -a; source .env; set +a   # dbt does not read .env itself
mkdir -p data/azurite "${DAGSTER_HOME:-.dagster_home}"

# --- python deps -------------------------------------------------------------
echo "==> uv sync (root + orchestration)"
uv sync --quiet
(cd orchestration && uv sync --quiet)

# --- azurite -----------------------------------------------------------------
if [[ "${STORAGE_MODE:-local}" == "azurite" ]]; then
  if docker ps --format '{{.Names}}' | grep -qx azurite; then
    echo "==> azurite already running"
  elif docker ps -a --format '{{.Names}}' | grep -qx azurite; then
    echo "==> starting azurite"
    docker start azurite >/dev/null
  else
    echo "==> creating azurite"
    docker run -d --name azurite --restart unless-stopped -p 127.0.0.1:10000:10000 -v "$ROOT/data/azurite:/data" \
      mcr.microsoft.com/azure-storage/azurite azurite-blob \
      --blobHost 0.0.0.0 --location /data --skipApiVersionCheck >/dev/null
  fi
  echo -n "==> waiting for azurite on :10000"
  for _ in $(seq 1 30); do
    (echo >/dev/tcp/127.0.0.1/10000) 2>/dev/null && break
    echo -n "."; sleep 1
  done
  echo
  uv run python scripts/create_containers.py
else
  echo "==> STORAGE_MODE=${STORAGE_MODE:-local}: skipping azurite"
fi

# --- optional one-off pipeline run ------------------------------------------
if [[ $BOOTSTRAP -eq 1 ]]; then
  echo "==> bootstrap pipeline"
  uv run python scripts/sync_bronze.py
  uv run python scripts/run_sql.py sql/silver_messages.sql
  uv run python scripts/run_sql.py sql/silver_tool_calls.sql
  uv run python scripts/run_sql.py sql/silver_bash_commands.sql
  (cd dbt && uv run dbt build --profiles-dir .)
  uv run python scripts/export_gold.py
  uv run python scripts/verify.py
fi

# --- servers -----------------------------------------------------------------
PIDS=()
cleanup() {
  echo; echo "==> stopping servers"
  for p in "${PIDS[@]:-}"; do [[ -n "$p" ]] && kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> refreshing dagster dbt defs"
(cd orchestration && uv run dg utils refresh-defs-state) || echo "warn: refresh-defs-state failed"

echo "==> dagster  -> http://localhost:3000"
(cd orchestration && exec uv run dg dev --host 127.0.0.1) &
PIDS+=($!)

echo "==> streamlit -> http://localhost:8501"
uv run streamlit run app/dashboard.py --server.headless true --server.address 127.0.0.1 &
PIDS+=($!)

wait
