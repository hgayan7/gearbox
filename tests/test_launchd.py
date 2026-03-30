import os
from pathlib import Path

import pytest

from core import launchd


class DummyCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_cron_schedule_to_calendar_entries_supports_ui_options():
    assert launchd.cron_schedule_to_calendar_entries("0 * * * *") == [{"Minute": 0}]
    assert launchd.cron_schedule_to_calendar_entries("47 10 * * *") == [{"Hour": 10, "Minute": 47}]
    assert launchd.cron_schedule_to_calendar_entries("0 11 * * 1-5") == [
        {"Weekday": 1, "Hour": 11, "Minute": 0},
        {"Weekday": 2, "Hour": 11, "Minute": 0},
        {"Weekday": 3, "Hour": 11, "Minute": 0},
        {"Weekday": 4, "Hour": 11, "Minute": 0},
        {"Weekday": 5, "Hour": 11, "Minute": 0},
    ]
    assert launchd.cron_schedule_to_calendar_entries("0 11 * * 0,6") == [
        {"Weekday": 0, "Hour": 11, "Minute": 0},
        {"Weekday": 6, "Hour": 11, "Minute": 0},
    ]


def test_cron_schedule_to_calendar_entries_rejects_per_minute_schedules():
    with pytest.raises(ValueError):
        launchd.cron_schedule_to_calendar_entries("* * * * *")

    with pytest.raises(ValueError):
        launchd.cron_schedule_to_calendar_entries("*/5 * * * *")


def test_sync_all_tasks_writes_active_plists_and_removes_inactive(monkeypatch, tmp_path):
    monkeypatch.setenv("GEARBOX_LAUNCH_AGENTS_DIR", str(tmp_path / "LaunchAgents"))

    launchctl_calls = []

    def fake_run(args, capture_output, text):
        launchctl_calls.append(args)
        return DummyCompletedProcess()

    monkeypatch.setattr("subprocess.run", fake_run)

    active_task = {
        "id": "active-task",
        "name": "Active Task",
        "schedule": "47 10 * * *",
        "is_paused": 0,
    }
    paused_task = {
        "id": "paused-task",
        "name": "Paused Task",
        "schedule": "0 11 * * *",
        "is_paused": 1,
    }

    orphan_plist = launchd.launch_agents_dir() / f"{launchd.TASK_LABEL_PREFIX}.orphan-task.plist"
    orphan_plist.parent.mkdir(parents=True, exist_ok=True)
    orphan_plist.write_text("orphan")

    paused_plist = launchd.task_plist_path(paused_task["id"])
    paused_plist.write_text("paused")

    launchd.sync_all_tasks([active_task, paused_task], "/usr/bin/python3", "/tmp/cli.py")

    assert launchd.task_plist_path(active_task["id"]).exists()
    assert not paused_plist.exists()
    assert not orphan_plist.exists()

    active_plist_bytes = launchd.task_plist_path(active_task["id"]).read_bytes()
    assert b"run-id" in active_plist_bytes
    assert b"active-task" in active_plist_bytes

    assert any(call[:2] == ["/bin/launchctl", "bootstrap"] for call in launchctl_calls)
    assert any(call[:2] == ["/bin/launchctl", "bootout"] for call in launchctl_calls)
