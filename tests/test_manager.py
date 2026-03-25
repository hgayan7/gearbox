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
