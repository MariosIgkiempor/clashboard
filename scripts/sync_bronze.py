"""Upload ~/.claude/projects/**/*.jsonl to the bronze container. Safe to re-run.

Object stores have no rsync, so the rule is ours: upload a file only when the blob
is missing or its size differs (transcripts are append-only, so a changed file grows).
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import blob_service

SOURCE = Path.home() / ".claude" / "projects"
# Transcripts rsynced from other machines: data/bronze_remote/<machine>/<project>/*.jsonl
# land in blob remote/<machine>/<project>/... so silver can tag rows with `machine`.
REMOTE = Path(__file__).resolve().parent.parent / "data" / "bronze_remote"
container = blob_service().get_container_client("bronze")

# One listing call instead of ~1,650 per-file lookups.
remote = {b.name: b.size for b in container.list_blobs()}


def sync(path: Path) -> tuple[str, int]:
    if path.is_relative_to(REMOTE):
        name = "remote/" + path.relative_to(REMOTE).as_posix()
    else:
        name = path.relative_to(SOURCE).as_posix()
    try:
        size = path.stat().st_size
        if remote.get(name) == size:
            return "skipped", 0
        with path.open("rb") as f:
            container.upload_blob(name, f, overwrite=True)
        return "uploaded", size
    except FileNotFoundError:  # transcript cleaned up mid-run
        return "vanished", 0


files = sorted([*SOURCE.rglob("*.jsonl"), *REMOTE.rglob("*.jsonl")])
counts = {"uploaded": 0, "skipped": 0, "vanished": 0}
uploaded_bytes = 0
with ThreadPoolExecutor(max_workers=8) as pool:
    for status, size in pool.map(sync, files):
        counts[status] += 1
        uploaded_bytes += size

print(f"local files: {len(files)}")
print(f"{counts}  uploaded {uploaded_bytes / 1e6:,.1f} MB")
