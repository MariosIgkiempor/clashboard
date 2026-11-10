#!/usr/bin/env bash
# Run on hefty (scheduled by deploy/install-hefty.sh): pull Claude Code transcripts from the MacBook.
# They land in data/bronze_remote/<MACHINE>/; the Dagster `new_transcripts` sensor refreshes the pipeline
# within ~5 minutes and silver rows are tagged machine=<MACHINE>.
# Never deletes locally (transcripts are append-only history; Claude Code prunes old ones on the MacBook).
# MacBook asleep / off the tailnet is normal: we log it and exit 0, the next run catches up.
#
# Config (env or .env): MACBOOK_HOST (Tailscale name), MACBOOK_USER, MACBOOK_MACHINE (tag).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }

HOST="${MACBOOK_HOST:-marios-macbook-pro}"
USER_="${MACBOOK_USER:-mario}"
MACHINE="${MACBOOK_MACHINE:-macbook-pro}"
DEST="$ROOT/data/bronze_remote/$MACHINE/"
mkdir -p "$DEST"

if rsync -a --prune-empty-dirs \
     -e "ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new" \
     --include='*/' --include='*.jsonl' --exclude='*' \
     "$USER_@$HOST:.claude/projects/" "$DEST"; then
  echo "$(date '+%F %T') pulled from $USER_@$HOST"
else
  echo "$(date '+%F %T') $USER_@$HOST unreachable or rsync failed (exit $?); will retry next run"
fi
exit 0
