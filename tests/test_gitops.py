import pytest
import json
from core import gitops
from core.manager import TaskManager

def test_export_spec_yaml_and_json(test_db):
    TaskManager.add_task(
        "Task 1",
        "0 9 * * *",
        "echo task1",
        timeout_seconds=30,
        requires_ac_power=True,
    )
    TaskManager.add_task(
        "Task 2",
        "file_watch",
        "echo task2",
        trigger_type="file_watch",
        watch_path="/tmp/test",
    )

    yaml_out = gitops.export_spec(format_type="yaml")
    assert "version: 1" in yaml_out
    assert "Task 1" in yaml_out
    assert "Task 2" in yaml_out
    assert "timeout_seconds: 30" in yaml_out
    assert "watch_path: /tmp/test" in yaml_out

    json_out = gitops.export_spec(format_type="json")
    parsed = json.loads(json_out)
    assert parsed["version"] == 1
    assert len(parsed["tasks"]) == 2

def test_load_spec_validates_and_normalizes():
    raw_yaml = """
version: 1
tasks:
  - name: Test YAML Task
    command: python3 run.py
    trigger:
      type: file_watch
      watch_path: /tmp/incoming
    safety:
      timeout_seconds: 45
      requires_ac_power: true
      prevent_sleep: true
    retries:
      max_retries: 2
      retry_delay: 5
    pipeline:
      on_success: Another Task
"""
    tasks = gitops.load_spec(raw_yaml)
    assert len(tasks) == 1
    t = tasks[0]
    assert t["name"] == "Test YAML Task"
    assert t["command"] == "python3 run.py"
    assert t["trigger_type"] == "file_watch"
    assert t["watch_path"] == "/tmp/incoming"
    assert t["timeout_seconds"] == 45
    assert t["requires_ac_power"] is True
    assert t["prevent_sleep"] is True
    assert t["max_retries"] == 2
    assert t["retry_delay_seconds"] == 5
    assert t["on_success"] == "Another Task"

def test_apply_spec_idempotent_and_prune(test_db, monkeypatch):
    monkeypatch.setattr("core.launchd.sync_all_tasks", lambda *args, **kwargs: [])

    raw_yaml = """
version: 1
tasks:
  - name: Initial Spec Task
    command: echo init
    trigger:
      schedule: 0 10 * * *
"""
    tasks = gitops.load_spec(raw_yaml)
    res1 = gitops.apply_spec(tasks)
    assert len(res1["created"]) == 1
    assert "Initial Spec Task" in res1["created"]

    # Re-applying should update, not re-create
    res2 = gitops.apply_spec(tasks)
    assert len(res2["created"]) == 0
    assert len(res2["updated"]) == 1

    # Adding a second task and pruning the first
    second_yaml = """
version: 1
tasks:
  - name: New Only Task
    command: echo new
    trigger:
      schedule: 0 12 * * *
"""
    new_tasks = gitops.load_spec(second_yaml)
    res3 = gitops.apply_spec(new_tasks, prune=True)
    assert "New Only Task" in res3["created"]
    assert "Initial Spec Task" in res3["pruned"]

    current_tasks = TaskManager.get_tasks()
    assert len(current_tasks) == 1
    assert current_tasks[0]["name"] == "New Only Task"
