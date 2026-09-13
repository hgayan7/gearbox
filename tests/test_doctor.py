import pytest
from core import doctor
from core.manager import TaskManager

def test_doctor_diagnostics(test_db):
    TaskManager.add_task("Doctor Task", "0 10 * * *", "echo doctor")
    diag = doctor.run_diagnostics(fix=False)

    assert "python" in diag
    assert diag["python"]["version_ok"] is True
    assert "storage" in diag
    assert diag["storage"]["db_exists"] is True
    assert diag["storage"]["db_writable"] is True
    assert "launchd" in diag

def test_doctor_auto_fix_permissions_and_path(test_db, tmp_path, monkeypatch):
    import core.config as config
    from pathlib import Path

    runtime_dir = Path(config.DB_PATH).parent
    runtime_dir.chmod(0o755)

    TaskManager.add_task(
        "Needs Path Task",
        "0 10 * * *",
        "node app.js",
    )

    diag = doctor.run_diagnostics(fix=True)
    assert len(diag["fixes_applied"]) > 0

    # Ensure runtime dir was secured
    assert (runtime_dir.stat().st_mode & 0o777) == 0o700
