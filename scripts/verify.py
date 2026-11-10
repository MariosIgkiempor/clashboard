"""Check that local files, Azurite and the dbt gold tables agree. Exit 1 on any failure.

    uv run python scripts/verify.py            # Azurite internal consistency
    uv run python scripts/verify.py --parity   # also require local silver == Azurite silver
                                               # (only valid right after rebuilding BOTH modes)
"""
import os
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from common import blob_service  # noqa: E402  (also loads .env)

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
failures = 0


def check(name: str, ok: bool, detail: str) -> None:
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")


# 1. Azurite reachable, containers exist
try:
    svc = blob_service()
    names = {c.name for c in svc.list_containers()}
    check("azurite containers", {"bronze", "silver", "gold"} <= names, str(sorted(names)))
except Exception as e:  # noqa: BLE001
    check("azurite reachable", False, f"{type(e).__name__}: {str(e)[:120]}")
    sys.exit(1)

# 2. bronze: same file count locally and in Azurite
source = Path.home() / ".claude" / "projects"
remote = Path(__file__).resolve().parent.parent / "data" / "bronze_remote"
local_files = sum(1 for _ in source.rglob("*.jsonl")) + sum(1 for _ in remote.rglob("*.jsonl"))
blob_files = sum(1 for _ in svc.get_container_client("bronze").list_blobs())
check("bronze file count", local_files == blob_files, f"~/.claude+remote={local_files} azurite={blob_files}")

con = duckdb.connect(str(ROOT / "data" / "clashboard.duckdb"), read_only=True)
con.execute("INSTALL azure; LOAD azure;")
conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"].replace("'", "''")
con.execute(f"CREATE SECRET azurite (TYPE azure, CONNECTION_STRING '{conn}')")


def n(sql: str) -> int:
    return con.execute(sql).fetchone()[0]


# 3. silver: local and Azurite built from the same bronze should match (opt-in)
for table in ["messages", "tool_calls"] if "--parity" in sys.argv else []:
    local = n(f"select count(*) from read_parquet('data/silver/{table}/*/*.parquet')")
    remote = n(f"select count(*) from read_parquet('az://silver/{table}/*/*.parquet')")
    check(f"silver {table} local == azurite", local == remote, f"local={local:,} azurite={remote:,}")

# 3b. every Bash tool call has exactly one parsed command, and nothing secret-looking survived redaction
bash_calls = n("select count(*) from read_parquet('az://silver/tool_calls/*/*.parquet') where tool_name = 'Bash'")
bash_rows = n("select count(*) from read_parquet('az://silver/bash_commands/*/*.parquet')")
check("silver bash_commands == Bash tool calls", bash_calls == bash_rows, f"tool_calls={bash_calls:,} bash_commands={bash_rows:,}")
leaks = n("""select count(*) from read_parquet('az://silver/bash_commands/*/*.parquet')
             where regexp_matches(command_redacted, '(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})')
                or regexp_matches(command_redacted, '(?i)(token|secret|password|passwd|api[_-]?key)\\s*[=:]\\s*[^\\s\\[]{6,}')""")
check("bash_commands redaction leftovers", leaks == 0, f"{leaks} suspicious rows")

# 4. silver messages in Azurite == what dbt loaded into gold
gold_msgs = n("select sum(msgs) from main.daily_usage")
silver_msgs = n("select count(*) from read_parquet('az://silver/messages/*/*.parquet')")
check("gold daily_usage msgs == silver", gold_msgs == silver_msgs, f"gold={gold_msgs:,} silver={silver_msgs:,}")

# 5. exported gold Parquet in Azurite == dbt gold tables
for table in sorted(p.stem for p in (ROOT / "dbt" / "models" / "gold").glob("*.sql")):
    a = n(f"select count(*) from main.{table}")
    b = n(f"select count(*) from read_parquet('az://gold/{table}.parquet')")
    check(f"gold {table} db == azurite", a == b, f"db={a:,} azurite={b:,}")

print("\nALL CHECKS PASSED" if not failures else f"\n{failures} CHECK(S) FAILED")
sys.exit(1 if failures else 0)
