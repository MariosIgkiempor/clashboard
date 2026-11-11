# Clashboard

A local dashboard for your **Claude Code usage**: spend, tokens, cache efficiency, tools, MCP servers, Bash commands,
activity patterns, and per-session drill-downs. It is built entirely from the transcripts Claude Code already writes
to disk, so there are no hooks or API keys to set up, and nothing leaves your machine.

> Cost figures are **API-equivalent value** computed from `dbt/seeds/prices.csv`, not a bill. On a subscription they
> show what your usage would have cost at API prices.

## What you get

A Streamlit dashboard (default <http://localhost:8501>) with nine tabs: Overview, Cost, Cache, Tools, Bash, MCP,
Activity, Projects, Sessions. The sidebar filters by machine and project (git worktrees are grouped under their repo).

A Dagster UI (default <http://localhost:3000>) shows the pipeline lineage and run history. It refreshes the data
automatically when new transcripts appear, plus a nightly full rebuild.

## How it works

Claude Code writes every conversation to `~/.claude/projects/<project>/<session>.jsonl`, including per-message token
usage and tool calls. Clashboard turns those files into a small warehouse using a bronze/silver/gold layout:

```
~/.claude/projects/**/*.jsonl                  (+ optional transcripts pulled from other machines)
        │  scripts/sync_bronze.py   upload files that are new or grew (append-only, idempotent)
        ▼
BRONZE  raw JSONL, never modified               Azurite blob container `bronze`
        │  sql/silver_*.sql         DuckDB: flatten JSON, typed columns, redact secrets in Bash commands
        ▼
SILVER  Parquet: messages, tool_calls,          Azurite container `silver`
        bash_commands
        │  dbt (dbt-duckdb)         models + tests: cost (joined to the prices seed), cache savings,
        ▼                           tool stats/latency, sessions, heatmap, ...
GOLD    20 tables in data/clashboard.duckdb     + exported to Parquet in container `gold`
        │
        ▼
Streamlit app (app/dashboard.py)               reads the DuckDB file read-only
```

- **Bronze is immutable**, so silver and gold can always be rebuilt from it. Parsers can be fixed and replayed.
- **Silver is a full rebuild** every run (fast; a few seconds to ~a minute for thousands of transcripts).
- **Dagster** (`orchestration/`) wraps each step as an asset and the dbt project as a component. The
  `new_transcripts` sensor starts a `full_refresh` run (at most one per 5 min) when any transcript file changes, and
  `nightly_refresh` rebuilds every night.
- **Azurite** is the Azure Blob Storage emulator, run in Docker. It plays the role of object storage so the pipeline
  can move to real Azure with only configuration changes. `STORAGE_MODE=local` uses plain folders under `data/`
  instead (see [RUNBOOK.md](RUNBOOK.md) for the extra steps that mode needs).
- **Multiple machines**: silver has a `machine` column (`local` for the machine running Clashboard, or a label for
  each machine whose transcripts you pull in).

### Privacy

Everything stays on your machine. Bash command text is stored (max 500 chars) after best-effort regex redaction of
tokens and secrets. Redaction is not a guarantee: run `uv run python scripts/check_redaction.py` after changing it,
and don't share `data/` or the DuckDB file. To stop storing command text entirely, see the Bash section of
[RUNBOOK.md](RUNBOOK.md).

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) (installs Python and dependencies for you)
- Docker (Docker Desktop or OrbStack), used only for Azurite
- Claude Code already used on this machine (so `~/.claude/projects` has transcripts)
- macOS or Linux. The optional always-on service installer is macOS-only (launchd).

### Run it

```bash
git clone <repo-url> clashboard && cd clashboard
cp .env.example .env              # defaults work as-is; see Configuration below
scripts/start.sh --bootstrap      # first run: starts Azurite, builds the whole pipeline, then starts the UIs
```

When it prints `streamlit -> http://localhost:8501`, open that. `Ctrl-C` stops the UIs (Azurite keeps running; stop
it with `docker stop azurite`).

On later runs just use `scripts/start.sh`. Dagster picks up new transcripts within about 5 minutes. To force an
update immediately, with the stack running, in another terminal:

```bash
scripts/refresh.sh --no-pull      # rebuild now (drop --no-pull to also pull remote machines first)
```

Notes:

- Claude Code deletes transcripts after ~30 days (`cleanupPeriodDays`). Clashboard keeps its own copy in
  `data/azurite/`, so history accumulates from the day you first run it. Keep `data/` if you want it.
- If a model's cost shows as missing, add its prices to `dbt/seeds/prices.csv` (USD per million tokens) and re-run.

## Configuration

All settings live in `.env` (copied from `.env.example`). Everything except the first two is optional.

| Variable | Default | Purpose |
|---|---|---|
| `STORAGE_MODE` | `azurite` | `azurite` (blob emulator in Docker) or `local` (folders under `data/`) |
| `AZURE_STORAGE_CONNECTION_STRING` | Azurite dev account | Storage connection. The default is Azurite's published dev key, not a secret |
| `CLAUDE_PROJECTS_DIR` | `~/.claude/projects` | Where Claude Code stores transcripts |
| `DASHBOARD_PORT` | `8501` | Streamlit port |
| `DAGSTER_PORT` | `3000` | Dagster port |
| `TIMEZONE` | `UTC` | Timezone for the activity heatmap and the nightly schedule (e.g. `America/New_York`) |
| `NIGHTLY_CRON` | `0 3 * * *` | When the nightly full rebuild runs (in `TIMEZONE`) |
| `REMOTE_HOST` / `REMOTE_USER` / `REMOTE_MACHINE` | unset | Pull transcripts from a second machine over ssh (below) |

Paths for data and the Dagster home are derived from the checkout location, so the repo can live anywhere.
After editing `.env`, restart `scripts/start.sh`.

## Optional: combine several machines

Run Clashboard on one machine and let it pull transcripts from your other machines over ssh. Set `REMOTE_HOST`,
`REMOTE_USER` and `REMOTE_MACHINE` (the label shown in the dashboard) in `.env`, make sure passwordless ssh works
(`ssh-copy-id user@host`), then run `scripts/pull_remote.sh` by hand or schedule it. Details are in
[deploy/README.md](deploy/README.md).

## Optional: run it as an always-on service (macOS)

```bash
deploy/install-service.sh         # launchd service, auto-restart, pulls remote machines every 15 min
```

If Tailscale is installed it also exposes the UIs on your tailnet over HTTPS; pass `--no-tailscale` to skip that.
See [deploy/README.md](deploy/README.md).

## Repo layout

| Path | What |
|---|---|
| `app/dashboard.py` | Streamlit dashboard |
| `scripts/` | `start.sh`, `refresh.sh`, bronze sync, SQL runner, gold export, `verify.py` consistency check |
| `sql/` | Bronze → silver DuckDB SQL |
| `dbt/` | Staging → intermediate → gold models, tests, and seeds (`prices.csv`, `command_families.csv`) |
| `orchestration/` | Dagster project: assets, `full_refresh` job, sensor, nightly schedule |
| `deploy/` | Optional launchd + Tailscale installer |
| `RUNBOOK.md` | Step-by-step manual pipeline, checks, troubleshooting |
| `PLAN.md` | Original design notes and roadmap |

## Troubleshooting

- **`docker daemon not running`**: start Docker Desktop / OrbStack.
- **Dashboard shows no data**: run `scripts/start.sh --bootstrap`, or `scripts/refresh.sh --no-pull` while it's up.
- **Anything else**: [RUNBOOK.md](RUNBOOK.md) has a symptom → fix table. `uv run python scripts/verify.py` checks
  that bronze, silver and gold agree.
