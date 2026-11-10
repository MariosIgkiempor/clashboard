import dagster as dg


# Safety net: a full rebuild every night, even if the sensor saw nothing.
@dg.schedule(
    job_name="full_refresh",
    cron_schedule="0 3 * * *",
    execution_timezone="Europe/London",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)
def nightly_refresh(context: dg.ScheduleEvaluationContext):
    return dg.RunRequest()
