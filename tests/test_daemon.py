import datetime as dt

import daemon
from tzlocal import get_localzone


class FakeJob:
    def __init__(self, job_id: str, next_run_time=None):
        self.id = job_id
        self.next_run_time = next_run_time


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


def test_sync_tasks_once_recovers_recent_missed_run_on_startup(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "47 10 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: "2026-03-27T10:47:00")
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 28, 10, 50, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 27, 22, 50, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(scheduler, {}, recovery_window_start=recovery_window_start)

    assert cron_map == {"task-1": "47 10 * * *"}
    assert recovered_runs == [("task-1", "echo hi")]


def test_sync_tasks_once_does_not_recover_without_prior_run_history(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "47 10 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: None)
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 28, 10, 50, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 27, 22, 50, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(scheduler, {}, recovery_window_start=recovery_window_start)

    assert cron_map == {"task-1": "47 10 * * *"}
    assert recovered_runs == []


def test_sync_tasks_once_does_not_recover_if_latest_run_already_covered_fire_time(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "47 10 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: "2026-03-28T10:49:57")
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 28, 10, 50, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 28, 10, 48, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(scheduler, {}, recovery_window_start=recovery_window_start)

    assert cron_map == {"task-1": "47 10 * * *"}
    assert recovered_runs == []


def test_sync_tasks_once_does_not_recover_when_missed_fire_is_outside_grace_window(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "47 10 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: "2026-03-27T10:47:00")
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 29, 23, 0, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 29, 10, 50, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(scheduler, {}, recovery_window_start=recovery_window_start)

    assert cron_map == {"task-1": "47 10 * * *"}
    assert recovered_runs == []


def test_sync_tasks_once_recovers_recent_missed_run_after_sleep_gap(monkeypatch):
    scheduler = FakeScheduler()
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "0 6 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: "2026-03-27T06:00:00")
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 28, 9, 0, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 27, 23, 0, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(scheduler, {}, recovery_window_start=recovery_window_start)

    assert cron_map == {"task-1": "0 6 * * *"}
    assert recovered_runs == [("task-1", "echo hi")]


def test_sync_tasks_once_recovers_after_sleep_gap_with_existing_job(monkeypatch):
    scheduler = FakeScheduler()
    scheduler.jobs["task-1_0"] = FakeJob("task-1_0")
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "0 6 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(daemon.TaskManager, "get_latest_run_started_at", lambda task_id: "2026-03-27T06:00:00")
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 28, 9, 0, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    recovery_window_start = dt.datetime(2026, 3, 27, 23, 0, tzinfo=scheduler.timezone)
    cron_map = daemon.sync_tasks_once(
        scheduler,
        {"task-1": "0 6 * * *"},
        recovery_window_start=recovery_window_start,
    )

    assert cron_map == {"task-1": "0 6 * * *"}
    assert recovered_runs == [("task-1", "echo hi")]
    assert scheduler.added == []
    assert scheduler.removed == []


def test_sync_tasks_once_recovers_overdue_existing_job_without_poll_gap(monkeypatch):
    scheduler = FakeScheduler()
    scheduler.jobs["task-1_0"] = FakeJob(
        "task-1_0",
        next_run_time=dt.datetime(2026, 3, 30, 10, 47, tzinfo=scheduler.timezone),
    )
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "47 10 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(
        daemon.TaskManager,
        "get_task_runs",
        lambda task_id, limit=1: [{"started_at": "2026-03-29T10:47:00", "status": "success"}],
    )
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 30, 11, 5, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    cron_map = daemon.sync_tasks_once(scheduler, {"task-1": "47 10 * * *"})

    assert cron_map == {"task-1": "47 10 * * *"}
    assert recovered_runs == [("task-1", "echo hi")]
    assert scheduler.removed == ["task-1_0"]
    assert scheduler.added[0]["id"] == "task-1_0"


def test_sync_tasks_once_reschedules_overdue_existing_job_after_manual_recovery(monkeypatch):
    scheduler = FakeScheduler()
    scheduler.jobs["task-1_0"] = FakeJob(
        "task-1_0",
        next_run_time=dt.datetime(2026, 3, 30, 11, 0, tzinfo=scheduler.timezone),
    )
    task = {
        "id": "task-1",
        "name": "Important Task",
        "schedule": "0 11 * * *",
        "command": "echo hi",
        "is_paused": 0,
    }
    recovered_runs = []

    monkeypatch.setattr(daemon.TaskManager, "get_tasks", lambda: [task])
    monkeypatch.setattr(
        daemon.TaskManager,
        "get_task_runs",
        lambda task_id, limit=1: [{"started_at": "2026-03-30T11:04:16", "status": "success"}],
    )
    monkeypatch.setattr(
        daemon,
        "_now_in_timezone",
        lambda timezone: dt.datetime(2026, 3, 30, 11, 5, tzinfo=timezone),
    )
    monkeypatch.setattr(daemon, "run_task", lambda task_id, command: recovered_runs.append((task_id, command)))

    cron_map = daemon.sync_tasks_once(scheduler, {"task-1": "0 11 * * *"})

    assert cron_map == {"task-1": "0 11 * * *"}
    assert recovered_runs == []
    assert scheduler.removed == ["task-1_0"]
    assert scheduler.added[0]["id"] == "task-1_0"


def test_get_recovery_window_start_uses_startup_lookback():
    timezone = get_localzone()
    now = dt.datetime(2026, 3, 28, 9, 0, tzinfo=timezone)

    recovery_window_start = daemon._get_recovery_window_start(None, now)

    assert recovery_window_start == now - dt.timedelta(seconds=daemon.MISFIRE_GRACE_TIME_SECONDS)


def test_get_recovery_window_start_uses_previous_sync_after_long_gap():
    timezone = get_localzone()
    previous_sync_at = dt.datetime(2026, 3, 28, 0, 0, tzinfo=timezone)
    now = dt.datetime(
        2026,
        3,
        28,
        0,
        0,
        tzinfo=timezone,
    ) + dt.timedelta(seconds=daemon.RECOVERY_WINDOW_THRESHOLD_SECONDS + 1)

    recovery_window_start = daemon._get_recovery_window_start(previous_sync_at, now)

    assert recovery_window_start == previous_sync_at


def test_get_recovery_window_start_skips_short_gap():
    timezone = get_localzone()
    previous_sync_at = dt.datetime(2026, 3, 28, 9, 0, tzinfo=timezone)
    now = previous_sync_at + dt.timedelta(seconds=daemon.SYNC_INTERVAL_SECONDS)

    recovery_window_start = daemon._get_recovery_window_start(previous_sync_at, now)

    assert recovery_window_start is None
