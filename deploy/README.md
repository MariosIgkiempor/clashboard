# Running Clashboard on hefty

## One-time (on hefty)
```bash
cd ~/Programming/personal/clashboard && git pull   # needs this branch merged
scripts/start.sh --bootstrap    # first run only: builds the pipeline from local ~/.claude + any rsynced data; Ctrl-C when the UIs are up
deploy/install-hefty.sh         # launchd service + `tailscale serve`
```
Needs Docker (OrbStack is fine), Tailscale with HTTPS certificates enabled for the tailnet (admin console > DNS), and Remote Login (ssh) enabled on hefty.

URLs from the MacBook: `https://hefty.sheep-corn.ts.net:8501` (Streamlit), `https://hefty.sheep-corn.ts.net:3000` (Dagster).

## Syncing from the MacBook Pro (automatic, hefty pulls)
`deploy/install-hefty.sh` installs a launchd job (`com.clashboard.pull`) that runs `scripts/pull_from_macbook.sh` every 15 minutes
(log: `~/Library/Logs/clashboard/pull.log`). If the MacBook is asleep or offline the run is skipped and the next one catches up.

One-time setup on the **MacBook**: System Settings > General > Sharing > **Remote Login** ON, then authorize hefty's key:
```bash
# on hefty (generate a key first if `ls ~/.ssh/id_ed25519.pub` is missing: ssh-keygen -t ed25519)
ssh-copy-id mario@marios-macbook-pro        # then check: ssh mario@marios-macbook-pro true
```
Override with `MACBOOK_HOST`, `MACBOOK_USER`, `MACBOOK_MACHINE` in `.env`. Files land in `data/bronze_remote/macbook-pro/`;
the `new_transcripts` Dagster sensor refreshes within ~5 min. MacBook rows show as `machine = macbook-pro`; hefty's own sessions are `local`.
Note: the MacBook only needs to be awake sometimes; Claude Code keeps transcripts ~30 days, so a few days offline loses nothing.

Optional one-time history seed: Claude Code deletes transcripts after ~30 days, so older history only lives in the MacBook's `data/azurite/`. Copy the MacBook's `data/bronze/` (if populated) or `data/azurite/` to hefty before the first bootstrap if you want it.
