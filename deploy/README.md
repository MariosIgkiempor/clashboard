# Running Clashboard on hefty

## One-time (on hefty)
```bash
cd ~/Programming/personal/clashboard && git pull   # needs this branch merged
scripts/start.sh --bootstrap    # first run only: builds the pipeline from local ~/.claude + any rsynced data; Ctrl-C when the UIs are up
deploy/install-hefty.sh         # launchd service + `tailscale serve`
```
Needs Docker (OrbStack is fine), Tailscale with HTTPS certificates enabled for the tailnet (admin console > DNS), and Remote Login (ssh) enabled on hefty.

URLs from the MacBook: `https://hefty.sheep-corn.ts.net:8501` (Streamlit), `https://hefty.sheep-corn.ts.net:3000` (Dagster).

## Syncing from the MacBook Pro
```bash
scripts/push_to_hefty.sh          # run on the MacBook; override with HEFTY_HOST / HEFTY_DIR / MACHINE
```
Files go to `data/bronze_remote/macbook-pro/`; the `new_transcripts` Dagster sensor refreshes within ~5 min (or materialize manually).
Rows from the MacBook show up as `machine = macbook-pro`; hefty's own sessions are `local`.

Optional one-time history seed: Claude Code deletes transcripts after ~30 days, so older history only lives in the MacBook's `data/azurite/`. Copy the MacBook's `data/bronze/` (if populated) or `data/azurite/` to hefty before the first bootstrap if you want it.
