import logging
import os
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
logger = logging.getLogger("gearbox.daemon")


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
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

def sync_tasks_once(scheduler: BackgroundScheduler, task_cron_map: dict[str, str]):
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

        if is_paused:
            for jid in task_job_ids:
                scheduler.remove_job(jid)
                active_jobs.pop(jid, None)
                logger.info("Removed paused job %s for task '%s'", jid, task["name"])
            task_cron_map.pop(task_id, None)
            continue

        needs_scheduling = not task_job_ids or task_cron_map.get(task_id) != cron_str
        if not needs_scheduling:
            continue

        for jid in task_job_ids:
            scheduler.remove_job(jid)
            active_jobs.pop(jid, None)
            logger.info("Removed outdated job %s for task '%s'", jid, task["name"])

        crons = [c.strip() for c in cron_str.split("|") if c.strip()]
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
            except ValueError as e:
                logger.error("Error scheduling task '%s' with cron '%s': %s", task["name"], cron, e)
                success = False

        if success:
            task_cron_map[task_id] = cron_str

    for job_id in list(active_jobs.keys()):
        parts = job_id.rsplit("_", 1)
        if len(parts) != 2 or parts[0] not in db_task_ids:
            scheduler.remove_job(job_id)
            active_jobs.pop(job_id, None)
            if len(parts) == 2:
                task_cron_map.pop(parts[0], None)
            logger.info("Removed orphaned job %s", job_id)

    return task_cron_map


def sync_tasks(scheduler: BackgroundScheduler):
    """Poll the database forever and keep APScheduler in sync."""
    task_cron_map = {}

    while True:
        try:
            task_cron_map = sync_tasks_once(scheduler, task_cron_map)
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
