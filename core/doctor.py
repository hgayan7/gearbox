from typing import Dict, Any, List, Optional
import os
import sys
import shutil
import sqlite3
import subprocess
from pathlib import Path

from . import config
from .manager import TaskManager
from .db import get_connection

COMMON_DEV_PATHS = [
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
    os.path.expanduser("~/.cargo/bin"),
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.bun/bin"),
]

def check_python_environment() -> Dict[str, Any]:
    req_packages = ["click", "apscheduler", "cron_descriptor", "yaml"]
    missing = []
    for pkg in req_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    return {
        "python_version": sys.version.split()[0],
        "version_ok": sys.version_info >= (3, 9),
        "executable": sys.executable,
        "missing_packages": missing,
    }

def check_storage() -> Dict[str, Any]:
    db_path = Path(config.DB_PATH)
    runtime_dir = db_path.parent
    db_exists = db_path.exists()
    db_writable = os.access(db_path, os.W_OK) if db_exists else False
    dir_mode = oct(runtime_dir.stat().st_mode & 0o777) if runtime_dir.exists() else None

    return {
        "db_path": str(db_path),
        "db_exists": db_exists,
        "db_writable": db_writable,
        "runtime_dir": str(runtime_dir),
        "dir_mode": dir_mode,
        "mode_secure": dir_mode == "0o700" if dir_mode else False,
    }

def check_launchd() -> Dict[str, Any]:
    agents_dir = Path(os.path.expanduser("~/Library/LaunchAgents"))
    agents_writable = os.access(agents_dir, os.W_OK) if agents_dir.exists() else False

    # Check launchctl list
    ui_running = False
    try:
        res = subprocess.run(["/bin/launchctl", "list"], capture_output=True, text=True)
        ui_running = "com.gearbox.ui" in res.stdout
    except Exception:
        pass

    # Check orphaned plists
    tasks = TaskManager.get_tasks()
    valid_ids = {t["id"] for t in tasks}
    orphaned_plists = []
    if agents_dir.exists():
        for plist in agents_dir.glob("com.gearbox.task.*.plist"):
            name = plist.stem
            task_id = name.replace("com.gearbox.task.", "")
            if task_id not in valid_ids:
                orphaned_plists.append(str(plist))

    return {
        "agents_dir": str(agents_dir),
        "agents_writable": agents_writable,
        "ui_service_loaded": ui_running,
        "orphaned_plists": orphaned_plists,
    }

def audit_task_paths() -> List[Dict[str, Any]]:
    tasks = TaskManager.get_tasks()
    findings = []

    standard_launchd_dirs = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]

    for t in tasks:
        cmd = t.get("raw_command") or t.get("command", "")
        parts = cmd.strip().split()
        if not parts:
            continue

        first_token = parts[0]
        # Ignore cd, if, while, for, export, etc.
        if first_token in ["cd", "if", "while", "for", "export", "[", "[["]:
            continue

        # Extract binary name if token is a path or command
        binary_name = os.path.basename(first_token)

        # Check if in standard launchd path
        in_standard = any((Path(d) / binary_name).exists() for d in standard_launchd_dirs)

        # Parse task environment
        env_dict = TaskManager._parse_environment_json(t.get("environment_json"))
        has_custom_path = "PATH" in env_dict

        # Check where it exists on system
        sys_loc = shutil.which(binary_name)

        if not in_standard and not has_custom_path:
            findings.append({
                "task_name": t["name"],
                "binary": binary_name,
                "found_at": sys_loc,
                "issue": f"Binary '{binary_name}' is not in default launchd PATH (/usr/bin:/bin).",
                "recommendation": "Inject developer PATH into task environment.",
            })

    return findings

def run_diagnostics(fix: bool = False) -> Dict[str, Any]:
    py = check_python_environment()
    storage = check_storage()
    ld = check_launchd()
    path_findings = audit_task_paths()

    fixes_applied = []

    if fix:
        # Fix permissions on runtime directory if needed
        runtime_dir = Path(config.DB_PATH).parent
        if runtime_dir.exists() and (runtime_dir.stat().st_mode & 0o777) != 0o700:
            runtime_dir.chmod(0o700)
            fixes_applied.append("Secured ~/.gearbox directory permissions to 0700.")

        # Clean orphaned plists
        for plist_path in ld["orphaned_plists"]:
            try:
                subprocess.run(["/bin/launchctl", "bootout", f"gui/{os.getuid()}", plist_path], capture_output=True)
                os.remove(plist_path)
                fixes_applied.append(f"Removed orphaned launchd plist: {os.path.basename(plist_path)}")
            except Exception:
                pass

        # Fix task PATH issues by injecting developer PATH
        dev_path_str = ":".join([p for p in COMMON_DEV_PATHS if os.path.isdir(p)] + ["/usr/bin", "/bin", "/usr/sbin", "/sbin"])
        for finding in path_findings:
            t = TaskManager.get_task_by_name(finding["task_name"])
            if t:
                env_dict = TaskManager._parse_environment_json(t.get("environment_json"))
                env_dict["PATH"] = dev_path_str
                import json
                TaskManager.update_task(
                    existing_name=t["name"],
                    name=t["name"],
                    schedule=t["schedule"],
                    command=t["command"],
                    raw_command=t.get("raw_command"),
                    working_directory=t.get("working_directory"),
                    environment_json=json.dumps(env_dict),
                    shell=t.get("shell"),
                    trigger_type=t.get("trigger_type") or "cron",
                    watch_path=t.get("watch_path"),
                    timeout_seconds=t.get("timeout_seconds") or 0,
                    max_retries=t.get("max_retries") or 0,
                    retry_delay_seconds=t.get("retry_delay_seconds") or 10,
                    requires_ac_power=bool(t.get("requires_ac_power")),
                    prevent_sleep=bool(t.get("prevent_sleep")),
                    on_success_task_id=t.get("on_success_task_id"),
                    on_failure_task_id=t.get("on_failure_task_id"),
                )
                fixes_applied.append(f"Injected developer PATH into task '{t['name']}'.")

    return {
        "python": py,
        "storage": storage,
        "launchd": ld,
        "path_findings": path_findings,
        "fixes_applied": fixes_applied,
    }
