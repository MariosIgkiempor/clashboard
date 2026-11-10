import subprocess
import sys
from pathlib import Path

import dagster as dg

ROOT = Path(__file__).resolve().parents[5]  # repo root


def run_script(context: dg.AssetExecutionContext, *args: str) -> None:
    cmd = [sys.executable, *args]
    context.log.info("running: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if proc.stdout:
        context.log.info(proc.stdout)
    if proc.returncode != 0:
        raise dg.Failure(description=f"{args[0]} failed", metadata={"stderr": proc.stderr[-2000:]})


@dg.asset(group_name="bronze", kinds={"python", "azure"})
def bronze_transcripts(context: dg.AssetExecutionContext) -> None:
    run_script(context, "scripts/sync_bronze.py")


@dg.asset(deps=[bronze_transcripts], group_name="silver", kinds={"duckdb", "azure"})
def silver_messages(context: dg.AssetExecutionContext) -> None:
    run_script(context, "scripts/run_sql.py", "sql/silver_messages.sql")


@dg.asset(deps=[bronze_transcripts], group_name="silver", kinds={"duckdb", "azure"})
def silver_tool_calls(context: dg.AssetExecutionContext) -> None:
    run_script(context, "scripts/run_sql.py", "sql/silver_tool_calls.sql")


@dg.asset(deps=[bronze_transcripts], group_name="silver", kinds={"duckdb", "azure"})
def silver_bash_commands(context: dg.AssetExecutionContext) -> None:
    """Bash tool inputs with secrets redacted before they are stored."""
    run_script(context, "scripts/run_sql.py", "sql/silver_bash_commands.sql")


GOLD = sorted(p.stem for p in (ROOT / "dbt" / "models" / "gold").glob("*.sql"))  # every gold model


@dg.asset(deps=[dg.AssetKey(t) for t in GOLD], group_name="gold", kinds={"duckdb", "azure"})
def gold_parquet_export(context: dg.AssetExecutionContext) -> None:
    run_script(context, "scripts/export_gold.py")

