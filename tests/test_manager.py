import pytest
from core.manager import TaskManager
from core.db import get_connection

def test_add_task(test_db):
    """Test adding a task."""
    task_id = TaskManager.add_task("Test Task", "*/5 * * * *", "echo 'hello'")
    assert task_id is not None
    
    tasks = TaskManager.get_tasks()
    assert len(tasks) == 1
    assert tasks[0]["name"] == "Test Task"
    assert tasks[0]["schedule"] == "*/5 * * * *"

def test_remove_task(test_db):
    """Test removing a task."""
    TaskManager.add_task("To Remove", "* * * * *", "ls")
    assert TaskManager.remove_task("To Remove") is True
    assert len(TaskManager.get_tasks()) == 0
    assert TaskManager.remove_task("Non Existent") is False

def test_get_task_by_name(test_db):
    """Test getting a task by name."""
    TaskManager.add_task("Find Me", "* * * * *", "pwd")
    task = TaskManager.get_task_by_name("Find Me")
    assert task is not None
    assert task["name"] == "Find Me"
    
    assert TaskManager.get_task_by_name("Not There") is None


def test_get_task_by_id(test_db):
    task_id = TaskManager.add_task("By Id", "0 11 * * *", "pwd")

    task = TaskManager.get_task_by_id(task_id)

    assert task is not None
    assert task["id"] == task_id
    assert task["name"] == "By Id"

def test_set_pause_status(test_db):
    """Test pausing and resuming a task."""
    TaskManager.add_task("Pause Test", "* * * * *", "date")
    
    assert TaskManager.set_pause_status("Pause Test", True) is True
    task = TaskManager.get_task_by_name("Pause Test")
    assert task["is_paused"] == 1
    
    assert TaskManager.set_pause_status("Pause Test", False) is True
    task = TaskManager.get_task_by_name("Pause Test")
    assert task["is_paused"] == 0

def test_logging_runs(test_db):
    """Test logging run starts and ends."""
    task_id = TaskManager.add_task("Log Test", "* * * * *", "whoami")
    
    run_id = TaskManager.log_run_start(task_id)
    assert run_id is not None
    
    runs = TaskManager.get_task_runs(task_id)
    assert len(runs) == 1
    assert runs[0]["status"] == "running"
    
    TaskManager.log_run_end(run_id, "success", 0, "output", "")
    runs = TaskManager.get_task_runs(task_id)
    assert runs[0]["status"] == "success"
    assert runs[0]["exit_code"] == 0
    assert runs[0]["stdout"] == "output"

def test_reconcile_stale_runs_marks_dead_process_failed(test_db, monkeypatch):
    task_id = TaskManager.add_task("Stale Run", "* * * * *", "echo 'hello'")
    run_id = TaskManager.log_run_start(task_id)
    TaskManager.update_run_pid(run_id, 12345)

    monkeypatch.setattr(TaskManager, "_pid_exists", staticmethod(lambda pid: False))

    reconciled = TaskManager.reconcile_stale_runs()

    assert reconciled == 1
    runs = TaskManager.get_task_runs(task_id)
    assert runs[0]["status"] == "failed"
    assert runs[0]["exit_code"] == -2

def test_reconcile_stale_runs_keeps_live_process_running(test_db, monkeypatch):
    task_id = TaskManager.add_task("Live Run", "* * * * *", "echo 'hello'")
    run_id = TaskManager.log_run_start(task_id)
    TaskManager.update_run_pid(run_id, 12345)

    monkeypatch.setattr(TaskManager, "_pid_exists", staticmethod(lambda pid: True))

    reconciled = TaskManager.reconcile_stale_runs()

    assert reconciled == 0
    runs = TaskManager.get_task_runs(task_id)
    assert runs[0]["status"] == "running"


def test_get_latest_run_started_at_returns_most_recent_start(test_db):
    task_id = TaskManager.add_task("Latest Run", "* * * * *", "echo 'hello'")
    first_run_id = TaskManager.log_run_start(task_id)
    TaskManager.log_run_end(first_run_id, "success", 0, "first", "")
    latest_run_id = TaskManager.log_run_start(task_id)

    latest_started_at = TaskManager.get_latest_run_started_at(task_id)
    latest_run = TaskManager.get_task_runs(task_id, limit=1)[0]

    assert latest_started_at == latest_run["started_at"]
    assert latest_run["id"] == latest_run_id


def test_execute_task_skips_duplicate_running_task(test_db, monkeypatch):
    task_id = TaskManager.add_task("No Duplicate", "0 11 * * *", "echo 'hello'")
    TaskManager.log_run_start(task_id)

    def fail_log_run_start(task_id):
        raise AssertionError("should not start a duplicate run")

    monkeypatch.setattr(TaskManager, "log_run_start", staticmethod(fail_log_run_start))

    assert TaskManager.execute_task(task_id, "echo 'hello'") is False
