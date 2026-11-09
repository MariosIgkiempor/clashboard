# Clashboard plan (v2: data-engineering learning project)

Goal: learn data engineering, then Azure, by building a usage dashboard over my own Claude Code logs.
Local first. Azure last, as a migration of something that already works.

## Source of truth

Claude Code already writes everything to `~/.claude/projects/**/*.jsonl` (this machine: 1,646 files, 1.9 GB; each assistant message has `usage` with input/output/cache/thinking tokens; tool calls and outputs are in the same files). No hooks needed to capture. Hooks come back at the end only as a "run the pipeline now" trigger.

## Tool verdicts

| Tool | Use? | Why |
|---|---|---|
| **Parquet** | Yes | Columnar format. Right for this data, same format you will use in Azure. |
| **DuckDB** | Yes (core) | Reads JSONL and Parquet with SQL, no server. Replaces Postgres for analytics. |
| **dbt (dbt-duckdb)** | Yes | Teaches SQL modeling, tests, lineage, the layered (bronze/silver/gold) pattern. |
| **Evidence.dev** or **Metabase** | Yes | Dashboards straight off DuckDB. Replaces Laravel (see decision below). |
| **Azurite** (Azure Blob emulator) | Yes, phase 4 | Object-storage API you will use in Azure. Note: no ADLS Gen2 hierarchical namespace. |
| **MinIO** | Skip | Teaches the S3 API; your target is Azure. Its free community edition has also been scaled back (verify before relying on it). |
| **Dagster** | Later (phase 5) | Orchestration + asset lineage. Overkill until the pipeline has more than one step. |
| **Delta Lake / Iceberg** | Optional, last | Table formats on top of Parquet. Real concept, no real need at 2 GB. |
| Spark, Kafka, Airflow | No | Data is far too small. They add ops work and teach nothing this project needs. |

Honest scale check: 2 GB raw becomes a few hundred MB of Parquet. The project is a *pattern* exercise, not a scale one. That is fine.

## Decision: Laravel

Drop it for v1. The dashboard needs to query Parquet/DuckDB, and Laravel has no good path to that. Add it back later only as a thin API/UI if you want. Say so if you disagree.

## Architecture (medallion layers)

```
~/.claude/projects/*.jsonl
        |  ingest.py (incremental, idempotent by message uuid)
        v
BRONZE  raw JSONL copied as-is, partitioned by date        data/bronze/dt=YYYY-MM-DD/
        |  parse.py (flatten, typed columns, drop unknown types safely)
        v
SILVER  parquet: messages, tool_calls, sessions            data/silver/<table>/dt=.../*.parquet
        |  dbt models + tests (DuckDB)
        v
GOLD    daily_usage, cache_efficiency, tool_stats,         data/gold/*.parquet
        mcp_stats, session_summary, cost (prices table)
        |
        v
Evidence / Metabase dashboards
```

Rules:
- Bronze is never edited, so silver/gold can always be rebuilt (learn: reprocessing).
- Idempotent: re-running changes nothing.
- Cost computed in gold from a `prices` seed, never stored in silver.
- Redact secrets before silver. Tool outputs: keep size + short preview, not the full text.

## Local to Azure map (so phases 1 to 5 transfer)

| Local | Azure |
|---|---|
| folders under `data/` | Blob Storage / ADLS Gen2 containers |
| Azurite | Blob Storage |
| Python scripts / Dagster | Container Apps Jobs (or Data Factory) |
| DuckDB + dbt | same, reading from Blob (or Synapse/Fabric as a stretch) |
| Evidence/Metabase | Container Apps / Static Web Apps |
| `.env` | Key Vault |

Cost: Blob cool tier + one Container Apps Job on a schedule is roughly a few dollars/month (verify in the Azure calculator). No always-on VM needed.

## Phases

| # | Phase | You learn | Done when | Estimate |
|---|---|---|---|---|
| 0 | DuckDB reads `~/.claude/projects/**/*.jsonl` directly | DuckDB, `read_json_auto`, nested JSON | Query: tokens per day per model | 1 hour |
| 1 | Bronze to Silver: Python ingest + parse, partitioned Parquet | Parquet, partitioning, idempotency, schema drift | Re-run is a no-op; unknown record types do not crash | 1 day |
| 2 | Gold with dbt-duckdb: models, tests, `prices` seed | Modeling, dbt tests, lineage docs | `dbt build` green; `dbt docs` shows lineage | 1 day |
| 3 | Dashboards (Evidence) | BI over a lakehouse | Spend/day, cache ratio, top tools, MCP usage, session drill-down | half day |
| 4 | Move bronze/silver to Azurite | Object storage API, DuckDB reading remote storage | Pipeline runs against Azurite with only config changes | half day |
| 5 | Dagster: incremental assets, schedule, Claude `Stop` hook trigger | Orchestration, backfills | New session shows up in dashboard without manual runs | 1 day |
| 6 | Azure: Blob + Container Apps Job + Key Vault, Tailscale or Entra for access | Real cloud deploy, IAM, cost control | Runs nightly in Azure; budget alert set | 1 to 2 days |
| 7 | Optional: Delta/Iceberg, OTel live stream | Table formats, streaming vs batch | n/a | open |

## Risks

- JSONL format is undocumented and changes (this machine already has record types like `api-request`, `cost-state`). Bronze keeps raw data so parsers can be fixed and replayed.
- Secrets in tool outputs: redact before silver; never expose bronze through the dashboard.
- Subscription vs API billing: cost is an equivalent-value metric on a subscription.
- Multiple machines: add a `machine` column in silver from day one.

## Open questions

1. Evidence.dev (SQL + markdown, code-first) or Metabase (click-UI, Docker)? Default: Evidence.
2. Single machine for now? Default: yes.
