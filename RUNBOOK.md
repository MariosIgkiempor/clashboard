# Clashboard runbook

All commands run from the project root unless stated. Load config in every new terminal:

```bash
set -a; source .env; set +a      # AZURE_STORAGE_CONNECTION_STRING, STORAGE_MODE
```

`STORAGE_MODE=local` reads/writes `data/{bronze,silver,gold}`. `STORAGE_MODE=azurite` uses the Azurite containers. Python scripts read `.env` themselves; **dbt does not**, so always `source .env` before dbt.

## 0. Is the infrastructure up? (1 min)

```bash
docker ps --format '{{.Names}} {{.Status}}' | grep azurite     # expect: azurite Up ...
docker start azurite                                           # if it is not listed
```

If Azurite was ever recreated, it needs `--skipApiVersionCheck`:

```bash
docker run -d --name azurite -p 10000:10000 -v "$PWD/data/azurite:/data" \
  mcr.microsoft.com/azure-storage/azurite azurite-blob --blobHost 0.0.0.0 --location /data --skipApiVersionCheck
```

## 1. Full pipeline, Azurite mode (about 1 min)

| # | Command | Expect |
|---|---|---|
| 1 | `uv run python scripts/create_containers.py` | `exists` x3 (or `created` on first run) |
| 2 | `uv run python scripts/sync_bronze.py` | `uploaded` = only files that grew; `local files` = `skipped + uploaded` |
| 3 | `uv run python scripts/run_sql.py sql/silver_messages.sql` | `[azurite] ... wrote N rows` |
| 4 | `uv run python scripts/run_sql.py sql/silver_tool_calls.sql` | `[azurite] ... wrote N rows` |
| 4b | `uv run python scripts/run_sql.py sql/silver_bash_commands.sql` | `wrote N rows`; N equals the number of `Bash` tool calls |
| 5 | `(cd dbt && uv run dbt build --profiles-dir .)` | `PASS=48 WARN=0 ERROR=0` |
| 6 | `uv run python scripts/export_gold.py` | one line per gold model (16), `-> az://gold/<table>.parquet` |
| 7 | `uv run python scripts/verify.py` | `ALL CHECKS PASSED` |
| 8 | `uv run streamlit run app/dashboard.py` | 9 tabs, charts render, no red error boxes |

Step 7 is the single "is everything consistent?" check. It compares:
bronze file counts, silver (Azurite) vs dbt gold, and every exported gold Parquet vs its dbt table.
Local-vs-Azurite silver parity is opt-in (`verify.py --parity`, section 3), because local silver goes stale when only the Azurite pipeline (or Dagster) runs.

Row counts grow over time (active sessions append to transcripts), so compare *between* checks, not against fixed numbers. Run steps 2 to 7 back to back so nothing drifts in between.

### Bash command data and secrets

`silver_bash_commands` stores the Bash command text (redacted, max 500 chars) so the dashboard can drill into it.
Redaction is best-effort regex, not a guarantee. After any change to `sql/silver_bash_commands.sql` run:

```bash
uv run python scripts/check_redaction.py     # leftover counts must all be 0; shows redacted samples only
```

`verify.py` also fails if a token-shaped string survives in `bash_commands`. To stop storing command text at all,
drop `command_redacted` from the silver SQL and `command_preview` from `dbt/models/*/int_bash_commands.sql` and `bash_command_log.sql`.

## 2. Idempotency checks (3 min)

```bash
uv run python scripts/sync_bronze.py     # run it twice: 2nd run must print uploaded 0
uv run python scripts/run_sql.py sql/silver_messages.sql
uv run python scripts/run_sql.py sql/silver_messages.sql   # same row count both times
```

## 3. Local vs Azurite parity (3 min)

Proves the only difference between the two modes is `STORAGE_MODE`.

```bash
rsync -a --include='*/' --include='*.jsonl' --exclude='*' ~/.claude/projects/ data/bronze/
uv run python scripts/sync_bronze.py
for m in local azurite; do
  STORAGE_MODE=$m uv run python scripts/run_sql.py sql/silver_messages.sql
  STORAGE_MODE=$m uv run python scripts/run_sql.py sql/silver_tool_calls.sql
done
```

Expect identical row counts for `local` and `azurite`. `uv run python scripts/verify.py --parity` asserts the same.

dbt in both modes (the total must be the same):

```bash
cd dbt
for m in local azurite; do
  STORAGE_MODE=$m uv run dbt build --profiles-dir . | grep "Done\."
  duckdb -no-agent ../data/clashboard.duckdb -c "select round(sum(cost_usd),2) as total_cost from main.cost"
done
cd ..
```

## 4. Look at the data yourself

```bash
# What is in Azurite? (needs the secret each session)
duckdb -no-agent -c "
INSTALL azure; LOAD azure;
CREATE SECRET azurite (TYPE azure, CONNECTION_STRING '$AZURE_STORAGE_CONNECTION_STRING');
select count(*) from read_parquet('az://silver/messages/*/*.parquet');
select * from read_parquet('az://gold/cost.parquet') order by day desc limit 5;"
```

Gold tables in `data/clashboard.duckdb` need no secret. The `stg_*` views read silver, so querying them from a bare `duckdb` session in `azurite` mode fails with "No valid Azure credentials found"; query a gold table or create the secret first.

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Connection refused` / timeouts to `127.0.0.1:10000` | Azurite not running | `docker start azurite` |
| `API version ... is not supported by Azurite` | Azurite older than the SDK | Recreate it with `--skipApiVersionCheck` (section 0) |
| `KeyError: AZURE_STORAGE_CONNECTION_STRING` | `.env` not found | Run from the project root |
| dbt: `Env var required but not provided` | dbt does not read `.env` | `set -a; source .env; set +a` |
| `No valid Azure credentials found!` | Query touches `az://` with no secret | `CREATE SECRET` first, or query gold tables only |
| `Could not set lock on file ... clashboard.duckdb` | Another process is writing it | Wait for the dbt run to finish |
| `verify.py` bronze count FAIL | New transcript since the last sync | Re-run `sync_bronze.py` |
| `verify.py --parity` silver mismatch | Local silver is older than Azurite silver (or bronze changed between builds) | Rebuild both modes back to back (section 3) |
| New model name fails the `relationships` dbt test | No row in `dbt/seeds/prices.csv` | Add its prices, then `dbt build` |

## 6. Reset Azurite from scratch

```bash
docker rm -f azurite && rm -rf data/azurite    # deletes ALL blobs; bronze is re-uploadable from ~/.claude/projects
# then recreate it (section 0), and run section 1 steps 1 to 7
```

Bronze only re-uploads what still exists in `~/.claude/projects`. Claude Code deletes old transcripts after `cleanupPeriodDays` (default 30), so keep `data/azurite/` or `data/bronze/` if you want history.

## 7. Dagster (orchestration)

Start it (from the repo root; `.env` supplies `STORAGE_MODE`, the Azurite connection string; `scripts/start.sh` sets `DAGSTER_HOME` and `CLASHBOARD_DATA_DIR` from the checkout path):

```bash
cd orchestration && uv run dg dev          # UI at http://localhost:3000
```

| Check | How | Expect |
|---|---|---|
| Definitions load | `cd orchestration && uv run dg check defs` | `All definitions loaded successfully.` |
| Graph is right | UI > Assets > lineage | bronze -> silver_messages / silver_tool_calls -> stg_* -> gold -> gold_parquet_export |
| Manual run | UI > Assets > Materialize all (about 35 s) | all steps green; then `uv run python scripts/verify.py` passes |
| Sensor works | UI > Automation > `new_transcripts` is ON; use Claude Code, wait up to 5 min | a `full_refresh` run tagged `dagster/sensor_name: new_transcripts`; otherwise ticks say "no new transcript data" |
| Schedule exists | UI > Automation > `nightly_refresh` is ON | next tick 03:00 in `TIMEZONE` (default UTC) |
| History persists | stop and restart `dg dev` | old runs still listed (stored in `.dagster_home/`) |

After editing anything in `dbt/`: `cd orchestration && uv run dg utils refresh-defs-state` (the dbt component works from a cached copy).
After editing `.env`: restart `dg dev`.
To run on another port (e.g. a second instance): `uv run dg dev --port 3005`.
