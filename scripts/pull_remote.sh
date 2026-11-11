#!/usr/bin/env bash
# Pull Claude Code transcripts from ANOTHER machine over ssh (optional; skip if you only track this machine).
# They land in data/bronze_remote/<REMOTE_MACHINE>/; the Dagster `new_transcripts` sensor refreshes the pipeline
# within ~5 minutes and silver rows are tagged machine=<REMOTE_MACHINE>.
# Never deletes locally (transcripts are append-only history; Claude Code prunes old ones at the source).
# Remote asleep / offline is normal: we log it and exit 0, the next run catches up.
#
# Config (env or .env): REMOTE_HOST (hostname or Tailscale name), REMOTE_USER, REMOTE_MACHINE (tag, e.g. "laptop"),
# REMOTE_PROJECTS_DIR (default .claude/projects, relative to the remote home).
# Needs passwordless ssh to the remote (ssh-copy-id user@host).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/.env" ]] && { set -a; source "$ROOT/.env"; set +a; }

if [[ -z "${REMOTE_HOST:-}" ]]; then
  echo "REMOTE_HOST not set in .env; nothing to pull (single-machine setup)"
  exit 0
fi
USER_="${REMOTE_USER:-$USER}"
MACHINE="${REMOTE_MACHINE:-remote}"
SRC="${REMOTE_PROJECTS_DIR:-.claude/projects}"
DEST="$ROOT/data/bronze_remote/$MACHINE/"
mkdir -p "$DEST"

if rsync -a --prune-empty-dirs \
     -e "ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new" \
     --include='*/' --include='*.jsonl' --exclude='*' \
     "$USER_@$REMOTE_HOST:$SRC/" "$DEST"; then
  echo "$(date '+%F %T') pulled from $USER_@$REMOTE_HOST"
else
  echo "$(date '+%F %T') $USER_@$REMOTE_HOST unreachable or rsync failed (exit $?); will retry next run"
fi
exit 0
