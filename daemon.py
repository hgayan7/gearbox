import datetime
import logging
import os
from pathlib import Path
import sys
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.triggers.cron import CronTrigger
from tzlocal import get_localzone
from core.db import init_db
from core.manager import TaskManager

SYNC_INTERVAL_SECONDS = 10
MISFIRE_GRACE_TIME_SECONDS = int(os.getenv("GEARBOX_MISFIRE_GRACE_TIME_SECONDS", str(12 * 60 * 60)))
RECOVERY_WINDOW_THRESHOLD_SECONDS = int(
    os.getenv("GEARBOX_RECOVERY_WINDOW_THRESHOLD_SECONDS", str(SYNC_INTERVAL_SECONDS * 3))
)
logger = logging.getLogger("gearbox.daemon")


def configure_logging():
    log_dir = Path.home() / ".gearbox"
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = []

    try:
        handlers.append(logging.FileHandler(log_dir / "daemon.log"))
    except OSError:
        pass

    try:
        if sys.stdout and sys.stdout.isatty():
            handlers.append(logging.StreamHandler(sys.stdout))
    except Exception:
        pass

    if not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def log_job_event(event):
    if event.code == EVENT_JOB_MISSED:
        logger.warning("Job %s missed its scheduled run at %s", event.job_id, event.scheduled_run_time)
    elif event.exception:
        logger.exception("Job %s failed", event.job_id, exc_info=event.exception)
    else:
        logger.info("Job %s completed successfully", event.job_id)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        timezone=get_localzone(),
        job_defaults={
            "misfire_grace_time": MISFIRE_GRACE_TIME_SECONDS,
            "coalesce": True,
            "max_instances": 1,
        },
    )
    scheduler.add_listener(log_job_event, EVENT_JOB_MISSED | EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    return scheduler


def run_task(task_id: str, command: str):
    TaskManager.execute_task(task_id, command)


def _now_in_timezone(timezone) -> datetime.datetime:
    return datetime.datetime.now(timezone)


def _get_latest_scheduled_fire_time(trigger: CronTrigger, now: datetime.datetime, lookback_start: datetime.datetime):
    previous_fire_time = None
    cursor = lookback_start
    latest_fire_time = None

    while True:
        next_fire_time = trigger.get_next_fire_time(previous_fire_time, cursor)
        if next_fire_time is None or next_fire_time > now:
            return latest_fire_time

        latest_fire_time = next_fire_time
        previous_fire_time = next_fire_time
        cursor = next_fire_time


def _parse_datetime(value, timezone):
    if not value:
        return None

    if isinstance(value, datetime.datetime):
        parsed = value
    else:
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone)
    return parsed.astimezone(timezone)


def _recover_missed_run_if_needed(
    task: dict,
    cron_str: str,
    scheduler: BackgroundScheduler,
    recovery_window_start: datetime.datetime,
):
    last_started_at = TaskManager.get_latest_run_started_at(task["id"])
    if not last_started_at:
        return

    now = _now_in_timezone(scheduler.timezone)
    lookback_start = max(
        recovery_window_start,
        now - datetime.timedelta(seconds=MISFIRE_GRACE_TIME_SECONDS),
    )
    trigger = CronTrigger.from_crontab(cron_str, timezone=scheduler.timezone)
    latest_fire_time = _get_latest_scheduled_fire_time(trigger, now, lookback_start)
    if latest_fire_time is None or latest_fire_time >= now:
        return

    latest_run_started_at = _parse_datetime(last_started_at, scheduler.timezone)
    if latest_run_started_at is not None and latest_run_started_at >= latest_fire_time:
        return

    logger.warning(
        "Recovering missed run for task '%s' scheduled at %s",
        task["name"],
        latest_fire_time,
    )
    run_task(task["id"], task["command"])


def _get_overdue_job_fire_time(job, scheduler: BackgroundScheduler):
    next_run_time = _parse_datetime(getattr(job, "next_run_time", None), scheduler.timezone)
    if next_run_time is None:
        return None

    now = _now_in_timezone(scheduler.timezone)
    overdue_seconds = (now - next_run_time).total_seconds()
    if overdue_seconds <= RECOVERY_WINDOW_THRESHOLD_SECONDS:
        return None
    if overdue_seconds > MISFIRE_GRACE_TIME_SECONDS:
        return None

    return next_run_time


def _recover_overdue_job_if_needed(
    task: dict,
    cron_str: str,
    job,
    scheduler: BackgroundScheduler,
):
    overdue_fire_time = _get_overdue_job_fire_time(job, scheduler)
    if overdue_fire_time is None:
        return job

    latest_runs = TaskManager.get_task_runs(task["id"], limit=1)
    latest_run = latest_runs[0] if latest_runs else None
    latest_run_started_at = _parse_datetime(latest_run["started_at"], scheduler.timezone) if latest_run else None
    latest_run_status = latest_run["status"] if latest_run else None

    if latest_run_status == "running" and latest_run_started_at is not None and latest_run_started_at >= overdue_fire_time:
        return job

    if latest_run_started_at is None or latest_run_started_at < overdue_fire_time:
        logger.warning(
            "Recovering overdue scheduled job for task '%s' originally due at %s",
            task["name"],
            overdue_fire_time,
        )
        run_task(task["id"], task["command"])

    scheduler.remove_job(job.id)
    replacement_job = scheduler.add_job(
        run_task,
        trigger=CronTrigger.from_crontab(cron_str, timezone=scheduler.timezone),
        id=job.id,
        args=[task["id"], task["command"]],
        replace_existing=True,
        misfire_grace_time=MISFIRE_GRACE_TIME_SECONDS,
        coalesce=True,
        max_instances=1,
    )
    logger.warning(
        "Re-scheduled overdue job %s for task '%s'; next run at %s",
        replacement_job.id,
        task["name"],
        replacement_job.next_run_time,
    )
    return replacement_job


def sync_tasks_once(
    scheduler: BackgroundScheduler,
    task_cron_map: dict[str, str],
    recovery_window_start: datetime.datetime | None = None,
):
    """Sync active database tasks into APScheduler exactly once."""
    reconciled_runs = TaskManager.reconcile_stale_runs()
    if reconciled_runs:
        logger.warning("Reconciled %s stale running run(s)", reconciled_runs)

    tasks = TaskManager.get_tasks()
    active_jobs = {job.id: job for job in scheduler.get_jobs()}
    db_task_ids = set()

    for task in tasks:
        task_id = task["id"]
        db_task_ids.add(task_id)
        is_paused = bool(task["is_paused"])
        cron_str = task["schedule"]
        task_job_ids = [jid for jid in active_jobs.keys() if jid.startswith(task_id)]
        crons = [c.strip() for c in cron_str.split("|") if c.strip()]

        if is_paused:
            for jid in task_job_ids:
                scheduler.remove_job(jid)
                active_jobs.pop(jid, None)
                logger.info("Removed paused job %s for task '%s'", jid, task["name"])
            task_cron_map.pop(task_id, None)
            continue

        needs_scheduling = not task_job_ids or task_cron_map.get(task_id) != cron_str
        if needs_scheduling:
            for jid in task_job_ids:
                scheduler.remove_job(jid)
                active_jobs.pop(jid, None)
                logger.info("Removed outdated job %s for task '%s'", jid, task["name"])

            success = True
            for i, cron in enumerate(crons):
                try:
                    job = scheduler.add_job(
                        run_task,
                        trigger=CronTrigger.from_crontab(cron, timezone=scheduler.timezone),
                        id=f"{task_id}_{i}",
                        args=[task_id, task["command"]],
                        replace_existing=True,
                        misfire_grace_time=MISFIRE_GRACE_TIME_SECONDS,
                        coalesce=True,
                        max_instances=1,
                    )
                    logger.info(
                        "Scheduled task '%s' with cron '%s' as job %s; next run at %s",
                        task["name"],
                        cron,
                        job.id,
                        job.next_run_time,
                    )
                    active_jobs[job.id] = job
                except ValueError as e:
                    logger.error("Error scheduling task '%s' with cron '%s': %s", task["name"], cron, e)
                    success = False

            if not success:
                continue

            task_cron_map[task_id] = cron_str

        for i, cron in enumerate(crons):
            job_id = f"{task_id}_{i}"
            job = active_jobs.get(job_id)
            if job is not None:
                active_jobs[job_id] = _recover_overdue_job_if_needed(task, cron, job, scheduler)

            if recovery_window_start is not None:
                _recover_missed_run_if_needed(task, cron, scheduler, recovery_window_start)

    for job_id in list(active_jobs.keys()):
        parts = job_id.rsplit("_", 1)
        if len(parts) != 2 or parts[0] not in db_task_ids:
            scheduler.remove_job(job_id)
            active_jobs.pop(job_id, None)
            if len(parts) == 2:
                task_cron_map.pop(parts[0], None)
            logger.info("Removed orphaned job %s", job_id)

    return task_cron_map


def _get_recovery_window_start(
    previous_sync_at: datetime.datetime | None,
    now: datetime.datetime,
) -> datetime.datetime | None:
    if previous_sync_at is None:
        return now - datetime.timedelta(seconds=MISFIRE_GRACE_TIME_SECONDS)

    gap = (now - previous_sync_at).total_seconds()
    if gap > RECOVERY_WINDOW_THRESHOLD_SECONDS:
        logger.warning("Detected scheduler gap of %.1fs; recovering missed runs", gap)
        return previous_sync_at

    return None


def sync_tasks(scheduler: BackgroundScheduler):
    """Poll the database forever and keep APScheduler in sync."""
    task_cron_map = {}
    previous_sync_at = None

    while True:
        try:
            now = _now_in_timezone(scheduler.timezone)
            task_cron_map = sync_tasks_once(
                scheduler,
                task_cron_map,
                recovery_window_start=_get_recovery_window_start(previous_sync_at, now),
            )
            previous_sync_at = now
        except Exception:
            logger.exception("Sync error")

        time.sleep(SYNC_INTERVAL_SECONDS)

def main():
    configure_logging()
    init_db()
    scheduler = build_scheduler()
    scheduler.start()

    logger.info(
        "Gearbox daemon started with timezone=%s misfire_grace_time=%ss",
        scheduler.timezone,
        MISFIRE_GRACE_TIME_SECONDS,
    )

    try:
        sync_tasks(scheduler)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Gearbox daemon shutting down")
        scheduler.shutdown()

if __name__ == "__main__":
    main()
