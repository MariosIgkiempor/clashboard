# Running Clashboard as an always-on service (macOS, optional)

Not needed to try the app: `scripts/start.sh` is enough. Use this when you want it running on a
home server / always-on Mac, reachable from your other devices.

```bash
scripts/start.sh --bootstrap    # first run only: builds the pipeline; Ctrl-C once the UIs are up
deploy/install-service.sh       # launchd service (+ `tailscale serve` if Tailscale is installed)
deploy/install-service.sh --no-tailscale   # service only
```

Needs Docker (OrbStack is fine) when `STORAGE_MODE=azurite`. For Tailscale HTTPS, enable HTTPS certificates for your tailnet
(admin console > DNS). The UIs are then at `https://<this-host>.<tailnet>.ts.net:8501` (dashboard) and `:3000` (Dagster).
Without Tailscale, use an ssh tunnel: `ssh -L 8501:127.0.0.1:8501 user@host`.

Logs: `~/Library/Logs/clashboard/stack.log`. Stop: `launchctl bootout gui/$UID/com.clashboard.stack`.

## Combining several machines

Claude Code only writes transcripts on the machine you use it on. To see everything in one dashboard, run Clashboard on one
machine and have it **pull** transcripts from the others over ssh (repeat per extra machine by running `scripts/pull_remote.sh`
with different env, or rsync them into `data/bronze_remote/<name>/` however you like).

1. On the remote machine: enable ssh (macOS: System Settings > General > Sharing > Remote Login).
2. On the Clashboard host: `ssh-copy-id <user>@<host>` (create a key first with `ssh-keygen -t ed25519` if needed) and check `ssh <user>@<host> true`.
3. Set in `.env`: `REMOTE_HOST`, `REMOTE_USER`, `REMOTE_MACHINE` (the label shown in the dashboard).
4. `deploy/install-service.sh` then pulls every 15 minutes (log: `~/Library/Logs/clashboard/pull.log`); or run `scripts/pull_remote.sh` by hand.

Files land in `data/bronze_remote/<REMOTE_MACHINE>/`, and the `new_transcripts` Dagster sensor refreshes within ~5 minutes.
Rows from the remote show as `machine = <REMOTE_MACHINE>`; this machine's own are `local`. If the remote is asleep the run is
skipped and the next one catches up. Claude Code prunes transcripts after ~30 days, so a few days offline loses nothing.
