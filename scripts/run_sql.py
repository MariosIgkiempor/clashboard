"""Run a SQL file against the configured storage.

    uv run python scripts/run_sql.py sql/silver_messages.sql

STORAGE_MODE (from .env or the shell):
    local    -> {{bronze}} = data/bronze      {{silver}} = data/silver
    azurite  -> {{bronze}} = az://bronze      {{silver}} = az://silver

The silver output directory named in the COPY ... TO clause is deleted first,
so every run is a full, idempotent rebuild.
"""
import os
import re
import shutil
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
from common import blob_service  # noqa: E402  (also loads .env)

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)  # local paths in the SQL are relative to the project root

MODE = os.environ.get("STORAGE_MODE", "local")
ROOTS = {
    "local": {"bronze": "data/bronze", "silver": "data/silver"},
    "azurite": {"bronze": "az://bronze", "silver": "az://silver"},
}
if MODE not in ROOTS:
    sys.exit(f"STORAGE_MODE must be one of {list(ROOTS)}, got {MODE!r}")
roots = ROOTS[MODE]


def reset_output(sql: str) -> None:
    """Delete whatever the COPY ... TO '{{silver}}/<dir>' would write into."""
    for sub in re.findall(r"TO '\{\{silver\}\}/([^']+)'", sql):
        if MODE == "local":
            shutil.rmtree(Path(roots["silver"]) / sub, ignore_errors=True)
        else:
            container = blob_service().get_container_client("silver")
            names = [b.name for b in container.list_blobs(name_starts_with=sub + "/")]
            for i in range(0, len(names), 256):
                container.delete_blobs(*names[i : i + 256])
        print(f"reset {roots['silver']}/{sub}")


def main(path: str) -> None:
    sql = Path(path).read_text()
    reset_output(sql)
    for key, value in roots.items():
        sql = sql.replace("{{" + key + "}}", value)

    con = duckdb.connect()
    if MODE == "azurite":
        con.execute("INSTALL azure; LOAD azure;")
        conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"].replace("'", "''")
        con.execute(f"CREATE SECRET azurite (TYPE azure, CONNECTION_STRING '{conn}')")
    rows = con.execute(sql).fetchall()
    print(f"[{MODE}] {path}: wrote {rows[0][0]:,} rows")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
