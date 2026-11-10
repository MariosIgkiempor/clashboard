"""Audit the redaction in silver bash_commands. Prints counts and REDACTED text only.

    uv run python scripts/check_redaction.py
"""
import os
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: F401,E402  (loads .env)

con = duckdb.connect()
con.execute("INSTALL azure; LOAD azure;")
conn = os.environ["AZURE_STORAGE_CONNECTION_STRING"].replace("'", "''")
con.execute(f"CREATE SECRET a (TYPE azure, CONNECTION_STRING '{conn}')")
con.execute("create view b as select * from read_parquet('az://silver/bash_commands/*/*.parquet')")


def one(sql, params=None):
    return con.execute(sql, params or []).fetchone()[0]


print("bash_commands rows:", one("select count(*) from b"))
print("bash calls in silver tool_calls:",
      one("select count(*) from read_parquet('az://silver/tool_calls/*/*.parquet') where tool_name='Bash'"))
print("rows with a redaction marker:", one("select count(*) from b where command_redacted like '%[REDACTED]%'"))

# Anything that still looks like a secret after redaction should be 0.
leftovers = {
    "known token formats": r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[abprs]-)",
    "bearer value": r"(?i)bearer\s+[A-Za-z0-9._-]{12,}",
    "secret-name=value": r"(?i)(token|secret|password|passwd|api[_-]?key)\s*[=:]\s*[^\s\[]{6,}",
    "url credentials": r"://[^/\s:@\[]+:[^/\s@\[]+@",
}
for name, pattern in leftovers.items():
    print(f"leftover {name}:", one("select count(*) from b where regexp_matches(command_redacted, ?)", [pattern]))

print("\nsample of redacted rows (already redacted text):")
for (text,) in con.execute(
    "select left(command_redacted, 140) from b where command_redacted like '%[REDACTED]%' order by random() limit 8"
).fetchall():
    print("  -", repr(text))
