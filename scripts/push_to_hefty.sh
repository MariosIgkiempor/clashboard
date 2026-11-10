#!/usr/bin/env bash
# Run on the MacBook Pro: push Claude Code transcripts to hefty over Tailscale.
# They land in data/bronze_remote/<MACHINE>/ on hefty; the Dagster sensor there picks them up
# within ~5 minutes and silver rows are tagged machine=<MACHINE>.
# Never deletes on hefty (transcripts are append-only history; Claude Code prunes old ones locally).
set -euo pipefail
HOST="${HEFTY_HOST:-hefty}"                                   # Tailscale MagicDNS name
DEST="${HEFTY_DIR:-Programming/personal/clashboard}"         # checkout path relative to hefty's $HOME
MACHINE="${MACHINE:-macbook-pro}"
rsync -a --prune-empty-dirs --info=stats1 \
  --include='*/' --include='*.jsonl' --exclude='*' \
  "$HOME/.claude/projects/" "$HOST:$DEST/data/bronze_remote/$MACHINE/"
