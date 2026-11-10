"""Export every gold table from data/clashboard.duckdb to Parquet.

    STORAGE_MODE=local   -> data/gold/<table>.parquet
    STORAGE_MODE=azurite -> az://gold/<table>.parquet
"""
import os
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: F401,E402  (loads .env)

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

MODE = os.environ.get("STORAGE_MODE", "local")
GOLD_ROOT = {"local": "data/gold", "azurite": "az://gold"}[MODE]
TABLES = sorted(p.stem for p in (ROOT / "dbt" / "models" / "gold").glob("*.sql"))  # every gold model

if MODE == "local":
    Path(GOLD_ROOT).mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(ROOT / "data" / "clashboard.duckdb"), read_only=True)
if MODE == "azurite":
    con.execute("INSTALL azure; LOAD azure;")
    conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"].replace("'", "''")
    con.execute(f"CREATE SECRET azurite (TYPE azure, CONNECTION_STRING '{conn}')")

for table in TABLES:
    target = f"{GOLD_ROOT}/{table}.parquet"
    rows = con.execute(f"COPY (SELECT * FROM main.{table}) TO '{target}' (FORMAT parquet)").fetchone()[0]
    print(f"[{MODE}] {table:<18} {rows:>8,} rows -> {target}")
