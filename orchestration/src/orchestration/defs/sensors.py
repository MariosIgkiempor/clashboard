from pathlib import Path

import dagster as dg

SOURCE = Path.home() / ".claude" / "projects"
# Transcripts rsynced from other machines (see scripts/push_to_hefty.sh); same path as scripts/sync_bronze.py.
REMOTE = Path(__file__).resolve().parents[4] / "data" / "bronze_remote"
IN_PROGRESS = [
    dg.DagsterRunStatus.QUEUED,
    dg.DagsterRunStatus.NOT_STARTED,
    dg.DagsterRunStatus.STARTING,
    dg.DagsterRunStatus.STARTED,
]


@dg.sensor(
    job_name="full_refresh",
    minimum_interval_seconds=300,  # at most one run per 5 minutes while you are working
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def new_transcripts(context: dg.SensorEvaluationContext):
    """Start a refresh when any transcript has changed since the last run we triggered."""
    newest = max((p.stat().st_mtime for root in (SOURCE, REMOTE) for p in root.rglob("*.jsonl")), default=0.0)
    if newest <= float(context.cursor or 0):
        return dg.SkipReason("no new transcript data")

    busy = context.instance.get_runs(
        filters=dg.RunsFilter(job_name="full_refresh", statuses=IN_PROGRESS), limit=1
    )
    if busy:
        return dg.SkipReason("a refresh is already running")  # cursor unchanged: retry next tick

    context.update_cursor(str(newest))
    return dg.RunRequest(run_key=str(newest))
