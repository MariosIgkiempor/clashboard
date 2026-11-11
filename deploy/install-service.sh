#!/usr/bin/env bash
# macOS: run the whole stack as a launchd service (starts at login, restarts on crash).
#   - If REMOTE_HOST is set in .env, also installs a job that pulls that machine's transcripts every 15 min.
#   - If `tailscale` is installed, exposes the UIs on your tailnet over HTTPS (skip with --no-tailscale).
# Both servers bind 127.0.0.1; `tailscale serve` (or an ssh tunnel) is the only way in from other machines.
#   deploy/install-service.sh [--no-tailscale]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL=com.clashboard.stack
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

command -v uv >/dev/null || brew install uv
[[ -f "$ROOT/.env" ]] || { echo ".env missing in $ROOT" >&2; exit 1; }
set -a; source "$ROOT/.env"; set +a
mkdir -p "$ROOT/data/bronze_remote" "$HOME/Library/Logs/clashboard"

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/start.sh</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/clashboard/stack.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/clashboard/stack.log</string>
</dict></plist>
PL
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

if [[ -n "${REMOTE_HOST:-}" ]]; then
# Pull remote transcripts every 15 minutes (silently skipped while the remote is asleep/offline).
PULL_LABEL=com.clashboard.pull
PULL_PLIST="$HOME/Library/LaunchAgents/$PULL_LABEL.plist"
cat > "$PULL_PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$PULL_LABEL</string>
  <key>ProgramArguments</key><array><string>$ROOT/scripts/pull_remote.sh</string></array>
  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/clashboard/pull.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/clashboard/pull.log</string>
</dict></plist>
PL
launchctl bootout "gui/$UID/$PULL_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PULL_PLIST"
fi

if [[ "${1:-}" != "--no-tailscale" ]] && command -v tailscale >/dev/null; then
  tailscale serve --bg --https="${DASHBOARD_PORT:-8501}" "http://127.0.0.1:${DASHBOARD_PORT:-8501}"
  tailscale serve --bg --https="${DAGSTER_PORT:-3000}" "http://127.0.0.1:${DAGSTER_PORT:-3000}"
  tailscale serve status
fi
echo "logs: ~/Library/Logs/clashboard/stack.log   (first start needs: scripts/start.sh --bootstrap once, see deploy/README.md)"
