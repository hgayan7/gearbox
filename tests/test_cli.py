from click.testing import CliRunner
import json

from cli import cli
from core.manager import TaskManager


def test_run_bg_detaches_subprocess(monkeypatch):
    popen_calls = []

    class DummyProcess:
        pass

    def fake_popen(args, **kwargs):
        popen_calls.append((args, kwargs))
        return DummyProcess()

    monkeypatch.setattr(TaskManager, "get_task_by_name", staticmethod(lambda name: {
        "id": "task-1",
        "name": name,
        "command": "echo hi",
    }))

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = CliRunner().invoke(cli, ["run", "demo-task", "--bg"])

    assert result.exit_code == 0
    assert len(popen_calls) == 1
    _, kwargs = popen_calls[0]
    assert kwargs["close_fds"] is True
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] is not None
    assert kwargs["stdout"] is not None
    assert kwargs["stderr"] is not None


def test_preview_schedule_returns_normalized_schedule():
    result = CliRunner().invoke(cli, ["preview-schedule", "every 15 minutes"])

    assert result.exit_code == 0

    payload = json.loads(result.output)
    assert payload["normalized_schedule"] == "0 * * * * | 15 * * * * | 30 * * * * | 45 * * * *"
    assert payload["description"]
    assert len(payload["next_runs"]) == 3


def test_cli_add_and_update_with_advanced_options(monkeypatch):
    runner = CliRunner()

    # Add task with Part 1 flags
    result = runner.invoke(cli, [
        "add", "cli-part1-task", "0 10 * * *", "echo test",
        "--trigger-type", "file_watch",
        "--watch-path", "/tmp/watch",
        "--timeout", "45",
        "--max-retries", "3",
        "--retry-delay", "5",
        "--requires-ac",
        "--prevent-sleep",
    ])
    assert result.exit_code == 0
    assert "added task 'cli-part1-task'" in result.output

    task = TaskManager.get_task_by_name("cli-part1-task")
    assert task is not None
    assert task["trigger_type"] == "file_watch"
    assert task["watch_path"] == "/tmp/watch"
    assert task["timeout_seconds"] == 45
    assert task["max_retries"] == 3
    assert task["retry_delay_seconds"] == 5
    assert task["requires_ac_power"] == 1
    assert task["prevent_sleep"] == 1

    # Update task
    update_res = runner.invoke(cli, [
        "update", "cli-part1-task",
        "cli-part1-renamed", "0 10 * * *", "echo test",
        "--timeout", "90",
    ])
    assert update_res.exit_code == 0
    assert "Task 'cli-part1-task' updated" in update_res.output

    updated_task = TaskManager.get_task_by_name("cli-part1-renamed")
    assert updated_task is not None
    assert updated_task["timeout_seconds"] == 90


def test_cli_ls_displays_part1_info():
    runner = CliRunner()
    TaskManager.add_task(
        "ls-flags-task",
        "0 12 * * *",
        "echo flags",
        trigger_type="file_watch",
        watch_path="/tmp/watch",
        timeout_seconds=30,
        requires_ac_power=True,
        prevent_sleep=True,
        max_retries=2,
    )

    result = runner.invoke(cli, ["ls"])
    assert result.exit_code == 0
    assert "TRIGGER" in result.output
    assert "FLAGS" in result.output
    assert "Watch: /tmp/watch" in result.output
    assert "30s,AC,caff,retry:2" in result.output


def test_cli_history_displays_source_and_retry():
    runner = CliRunner()
    task_id = TaskManager.add_task("history-task", "0 12 * * *", "echo history")
    run_id = TaskManager.log_run_start(task_id, retry_count=1, trigger_source="retry")
    TaskManager.log_run_end(run_id, "success", 0, "done", "")

    result = runner.invoke(cli, ["history", "history-task"])
    assert result.exit_code == 0
    assert "SOURCE" in result.output
    assert "retry (r1)" in result.output

