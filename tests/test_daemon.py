import daemon
from tzlocal import get_localzone


class FakeJob:
    def __init__(self, job_id: str):
        self.id = job_id
        self.next_run_time = "next-run"


class FakeScheduler:
    def __init__(self):
        self.timezone = get_localzone()
        self.jobs = {}
        self.added = []
        self.removed = []

    def get_jobs(self):
        return list(self.jobs.values())

    def add_job(self, func, trigger, id, args, replace_existing, **kwargs):
        job = FakeJob(id)
        self.jobs[id] = job
        self.added.append(
            {
                "func": func,
                "trigger": trigger,
                "id": id,
                "args": args,
                "replace_existing": replace_existing,
                "kwargs": kwargs,
            }
        )
        return job

    def remove_job(self, job_id):
        self.jobs.pop(job_id, None)
        self.removed.append(job_id)


def test_build_scheduler_uses_safe_job_defaults():
    scheduler = daemon.build_scheduler()

    assert scheduler._job_defaults["misfire_grace_time"] == daemon.MISFIRE_GRACE_TIME_SECONDS
    assert scheduler._job_defaults["coalesce"] is True
    assert scheduler._job_defaults["max_instances"] == 1
    assert str(scheduler.timezone) == str(get_localzone())


def test_sync_tasks_once_schedules_active_tasks(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "0 11 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])

    cron_map = daemon.sync_tasks_once(scheduler, {})

    assert cron_map == {"task-1": "0 11 * * *"}
    assert "task-1_0" in scheduler.jobs
    assert scheduler.added[0]["kwargs"]["misfire_grace_time"] == daemon.MISFIRE_GRACE_TIME_SECONDS
    assert scheduler.added[0]["kwargs"]["coalesce"] is True
    assert scheduler.added[0]["kwargs"]["max_instances"] == 1


def test_sync_tasks_once_removes_paused_jobs(monkeypatch):
    scheduler = FakeScheduler()
    scheduler.jobs["task-1_0"] = FakeJob("task-1_0")
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "0 11 * * *",
        "command": "echo hi",
        "is_paused": 1,
    }
    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])

    cron_map = daemon.sync_tasks_once(scheduler, {"task-1": "0 11 * * *"})

    assert cron_map == {}
    assert scheduler.jobs == {}
    assert scheduler.removed == ["task-1_0"]


def test_sync_tasks_once_removes_orphaned_jobs(monkeypatch):
    scheduler = FakeScheduler()
    scheduler.jobs["task-1_0"] = FakeJob("task-1_0")
    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [])

    cron_map = daemon.sync_tasks_once(scheduler, {"task-1": "0 11 * * *"})

    assert cron_map == {}
    assert scheduler.jobs == {}
    assert scheduler.removed == ["task-1_0"]
