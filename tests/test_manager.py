import pytest
import json
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


def test_add_task_stores_advanced_execution_settings(test_db):
    task_id = TaskManager.add_task(
        "Advanced Task",
        "0 9 * * *",
        "cd '/tmp/demo' && echo hello",
        raw_command="echo hello",
        working_directory="/tmp/demo",
        environment_json='{"FOO":"bar"}',
        shell="/bin/bash",
    )

    task = TaskManager.get_task_by_id(task_id)

    assert task is not None
    assert task["command"] == "cd '/tmp/demo' && echo hello"
    assert task["raw_command"] == "echo hello"
    assert task["working_directory"] == "/tmp/demo"
    assert json.loads(task["environment_json"]) == {"FOO": "bar"}
    assert task["shell"] == "/bin/bash"


def test_update_task_rewrites_schedule_and_execution_settings(test_db):
    task_id = TaskManager.add_task("Original Task", "0 9 * * *", "echo before")

    updated_task_id = TaskManager.update_task(
        "Original Task",
        "Renamed Task",
        "15 10 * * 1-5",
        "cd '/tmp/demo' && python3 'job.py'",
        raw_command="python3 'job.py'",
        working_directory="/tmp/demo",
        environment_json='{"MODE":"prod"}',
        shell="/bin/zsh",
    )

    assert updated_task_id == task_id
    assert TaskManager.get_task_by_name("Original Task") is None

    task = TaskManager.get_task_by_name("Renamed Task")
    assert task is not None
    assert task["schedule"] == "15 10 * * 1-5"
    assert task["command"] == "cd '/tmp/demo' && python3 'job.py'"
    assert task["schedule_desc"]
    assert task["raw_command"] == "python3 'job.py'"
    assert task["working_directory"] == "/tmp/demo"
    assert json.loads(task["environment_json"]) == {"MODE": "prod"}
    assert task["shell"] == "/bin/zsh"

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

    def fail_log_run_start(task_id, **kwargs):
        raise AssertionError("should not start a duplicate run")

    monkeypatch.setattr(TaskManager, "log_run_start", staticmethod(fail_log_run_start))

    assert TaskManager.execute_task(task_id, "echo 'hello'") is False


def test_add_and_update_task_stores_part1_settings(test_db):
    task_id = TaskManager.add_task(
        "Part1 Task",
        "0 12 * * *",
        "echo part1",
        trigger_type="file_watch",
        watch_path="/tmp/incoming",
        timeout_seconds=60,
        max_retries=3,
        retry_delay_seconds=15,
        requires_ac_power=True,
        prevent_sleep=True,
    )

    task = TaskManager.get_task_by_id(task_id)
    assert task["trigger_type"] == "file_watch"
    assert task["watch_path"] == "/tmp/incoming"
    assert task["timeout_seconds"] == 60
    assert task["max_retries"] == 3
    assert task["retry_delay_seconds"] == 15
    assert task["requires_ac_power"] == 1
    assert task["prevent_sleep"] == 1

    # Update task settings
    TaskManager.update_task(
        "Part1 Task",
        "Part1 Task Updated",
        "0 18 * * *",
        "echo updated",
        trigger_type="cron",
        watch_path=None,
        timeout_seconds=120,
        max_retries=1,
        retry_delay_seconds=5,
        requires_ac_power=False,
        prevent_sleep=False,
    )

    updated = TaskManager.get_task_by_name("Part1 Task Updated")
    assert updated["trigger_type"] == "cron"
    assert updated["watch_path"] is None
    assert updated["timeout_seconds"] == 120
    assert updated["max_retries"] == 1
    assert updated["retry_delay_seconds"] == 5
    assert updated["requires_ac_power"] == 0
    assert updated["prevent_sleep"] == 0


def test_execute_task_ac_power_skips_when_on_battery(test_db, monkeypatch):
    task_id = TaskManager.add_task(
        "AC Required Task",
        "0 0 * * *",
        "echo heavy_work",
        requires_ac_power=True,
    )

    monkeypatch.setattr(TaskManager, "is_on_ac_power", staticmethod(lambda: False))

    result = TaskManager.execute_task(task_id)
    assert result is False

    runs = TaskManager.get_task_runs(task_id)
    assert len(runs) == 1
    assert runs[0]["status"] == "skipped"
    assert "requires AC power" in runs[0]["stdout"]


def test_execute_task_ac_power_runs_when_on_ac(test_db, monkeypatch):
    task_id = TaskManager.add_task(
        "AC Allowed Task",
        "0 0 * * *",
        "echo ac_ok",
        requires_ac_power=True,
    )

    monkeypatch.setattr(TaskManager, "is_on_ac_power", staticmethod(lambda: True))

    result = TaskManager.execute_task(task_id)
    assert result is True

    runs = TaskManager.get_task_runs(task_id)
    assert len(runs) == 1
    assert runs[0]["status"] == "success"


def test_execute_task_caffeinate_flag(test_db, monkeypatch):
    task_id = TaskManager.add_task(
        "Caffeinated Task",
        "0 0 * * *",
        "echo keep_awake",
        prevent_sleep=True,
    )

    recorded_args = []
    import subprocess
    original_popen = subprocess.Popen

    def mock_popen(args, **kwargs):
        recorded_args.append(args)
        return original_popen(args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    TaskManager.execute_task(task_id)

    assert len(recorded_args) == 1
    assert recorded_args[0][0] == "/usr/bin/caffeinate"
    assert recorded_args[0][1] == "-dimsu"


def test_execute_task_timeout_terminates_process(test_db):
    task_id = TaskManager.add_task(
        "Timeout Task",
        "0 0 * * *",
        "sleep 5",
        timeout_seconds=1,
    )

    result = TaskManager.execute_task(task_id)
    assert result is True

    runs = TaskManager.get_task_runs(task_id)
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["exit_code"] == -124
    assert "timed out after 1 seconds" in runs[0]["stdout"]


def test_execute_task_retry_mechanism(test_db):
    task_id = TaskManager.add_task(
        "Retry Task",
        "0 0 * * *",
        "exit 1",
        max_retries=2,
        retry_delay_seconds=0,
    )

    TaskManager.execute_task(task_id)

    runs = TaskManager.get_task_runs(task_id, limit=10)
    assert len(runs) == 3  # Initial attempt + 2 retries
    # Runs are returned in DESC order
    assert runs[0]["retry_count"] == 2
    assert runs[0]["trigger_source"] == "retry"
    assert runs[1]["retry_count"] == 1
    assert runs[1]["trigger_source"] == "retry"
    assert runs[2]["retry_count"] == 0
    assert runs[2]["trigger_source"] == "schedule"


def test_execute_task_workflow_chaining_on_success(test_db):
    successor_id = TaskManager.add_task("Successor Task", "0 0 * * *", "echo successor_ran")
    initial_id = TaskManager.add_task(
        "Initial Task",
        "0 0 * * *",
        "echo initial_ran",
        on_success_task_id=successor_id,
    )

    TaskManager.execute_task(initial_id)

    initial_runs = TaskManager.get_task_runs(initial_id)
    assert len(initial_runs) == 1
    assert initial_runs[0]["status"] == "success"

    successor_runs = TaskManager.get_task_runs(successor_id)
    assert len(successor_runs) == 1
    assert successor_runs[0]["status"] == "success"
    assert successor_runs[0]["trigger_source"] == "workflow_success"


def test_execute_task_workflow_chaining_on_failure(test_db):
    failure_handler_id = TaskManager.add_task("Failure Handler", "0 0 * * *", "echo handled_failure")
    initial_id = TaskManager.add_task(
        "Failing Task",
        "0 0 * * *",
        "exit 1",
        on_failure_task_id=failure_handler_id,
    )

    TaskManager.execute_task(initial_id)

    initial_runs = TaskManager.get_task_runs(initial_id)
    assert len(initial_runs) == 1
    assert initial_runs[0]["status"] == "failed"

    handler_runs = TaskManager.get_task_runs(failure_handler_id)
    assert len(handler_runs) == 1
    assert handler_runs[0]["status"] == "success"
    assert handler_runs[0]["trigger_source"] == "workflow_failure"

