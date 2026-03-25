import time
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from core.db import init_db
from core.manager import TaskManager

def run_task(task_id: str, command: str):
    TaskManager.execute_task(task_id, command)

def sync_tasks(scheduler: BackgroundScheduler):
    """Polls the database for active tasks and syncs them with APScheduler."""
    # Maps task_id -> raw cron string to track changes
    task_cron_map = {}
    
    while True:
        try:
            tasks = TaskManager.get_tasks()
            active_jobs = {job.id: job for job in scheduler.get_jobs()}
            
            db_task_ids = set()

            for task in tasks:
                task_id = task["id"]
                db_task_ids.add(task_id)
                is_paused = bool(task["is_paused"])
                cron_str = task["schedule"]
                
                # Identify all jobs belonging to this task
                task_job_ids = [jid for jid in active_jobs.keys() if jid.startswith(task_id)]
                
                if is_paused:
                    for jid in task_job_ids:
                        scheduler.remove_job(jid)
                        active_jobs.pop(jid, None)
                    task_cron_map.pop(task_id, None)
                    continue
                
                # Check if it needs scheduling
                needs_scheduling = False
                if not task_job_ids:
                    needs_scheduling = True
                elif task_cron_map.get(task_id) != cron_str:
                    needs_scheduling = True
                    
                if needs_scheduling:
                    # Clear out old ones
                    for jid in task_job_ids:
                        scheduler.remove_job(jid)
                        active_jobs.pop(jid, None)
                        
                    crons = [c.strip() for c in cron_str.split("|") if c.strip()]
                    success = True
                    for i, cron in enumerate(crons):
                        try:
                            scheduler.add_job(
                                run_task,
                                trigger=CronTrigger.from_crontab(cron),
                                id=f"{task_id}_{i}",
                                args=[task_id, task["command"]],
                                replace_existing=True
                            )
                        except ValueError as e:
                            print(f"Error scheduling task {task['name']} with cron {cron}: {e}")
                            success = False
                    
                    if success:
                        task_cron_map[task_id] = cron_str

            # Remove deleted jobs
            for job_id in list(active_jobs.keys()):
                parts = job_id.split('_')
                if parts[0] not in db_task_ids:
                    scheduler.remove_job(job_id)
                    task_cron_map.pop(parts[0], None)
                    
        except Exception as e:
            print(f"Sync error: {e}")
        
        # Poll every 10 seconds for DB changes
        time.sleep(10)

def main():
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.start()
    
    print("Gearbox Daemon started.")
    
    try:
        sync_tasks(scheduler)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    main()
