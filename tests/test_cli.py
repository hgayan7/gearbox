from click.testing import CliRunner

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
