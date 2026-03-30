import os
import plistlib
import subprocess
from pathlib import Path

from . import config


TASK_LABEL_PREFIX = "com.gearbox.task"


def launch_agents_dir() -> Path:
    override = os.getenv("GEARBOX_LAUNCH_AGENTS_DIR")
    if override:
        return Path(override)
    return Path.home() / "Library" / "LaunchAgents"


def launchd_logs_dir() -> Path:
    return config.GEARBOX_DIR / "launchd"


def launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def task_label(task_id: str) -> str:
    return f"{TASK_LABEL_PREFIX}.{task_id}"


def task_plist_path(task_id: str) -> Path:
    return launch_agents_dir() / f"{task_label(task_id)}.plist"


def _run_launchctl(arguments: list[str]) -> None:
    process = subprocess.run(
        ["/bin/launchctl", *arguments],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        stderr = (process.stderr or process.stdout or "").strip()
        raise RuntimeError(stderr or f"launchctl {' '.join(arguments)} failed")


def _try_run_launchctl(arguments: list[str]) -> None:
    try:
        _run_launchctl(arguments)
    except Exception:
        pass


def _parse_weekdays(field: str) -> list[int] | None:
    if field == "*":
        return None

    weekdays: list[int] = []
    for part in field.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_str, end_str = token.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            weekdays.extend(range(start, end + 1))
        else:
            weekdays.append(int(token))

    normalized = []
    for weekday in weekdays:
        normalized.append(0 if weekday == 7 else weekday)

    unique = sorted(set(normalized))
    if any(day < 0 or day > 6 for day in unique):
        raise ValueError(f"Unsupported weekday field: {field}")
    return unique


def _calendar_entries_for_cron(cron_expr: str) -> list[dict[str, int]]:
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Unsupported schedule format: {cron_expr}")

    minute, hour, day_of_month, month, day_of_week = parts
    if day_of_month != "*" or month != "*":
        raise ValueError(f"Unsupported schedule format: {cron_expr}")
    if minute == "*":
        raise ValueError("Per-minute schedules are no longer supported")
    if not minute.isdigit():
        raise ValueError(f"Unsupported minute field: {minute}")

    minute_value = int(minute)
    if minute_value < 0 or minute_value > 59:
        raise ValueError(f"Unsupported minute field: {minute}")

    if hour == "*":
        if day_of_week != "*":
            raise ValueError(f"Unsupported schedule format: {cron_expr}")
        return [{"Minute": minute_value}]

    if not hour.isdigit():
        raise ValueError(f"Unsupported hour field: {hour}")

    hour_value = int(hour)
    if hour_value < 0 or hour_value > 23:
        raise ValueError(f"Unsupported hour field: {hour}")

    weekdays = _parse_weekdays(day_of_week)
    if weekdays is None:
        return [{"Hour": hour_value, "Minute": minute_value}]

    return [{"Weekday": weekday, "Hour": hour_value, "Minute": minute_value} for weekday in weekdays]


def cron_schedule_to_calendar_entries(schedule: str) -> list[dict[str, int]]:
    entries: list[dict[str, int]] = []
    for cron_expr in [part.strip() for part in schedule.split("|") if part.strip()]:
        entries.extend(_calendar_entries_for_cron(cron_expr))

    if not entries:
        raise ValueError("Schedule is empty")

    deduped: list[dict[str, int]] = []
    seen = set()
    for entry in entries:
        key = tuple(sorted(entry.items()))
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    return deduped


def _plist_start_calendar_interval(schedule: str):
    entries = cron_schedule_to_calendar_entries(schedule)
    if len(entries) == 1:
        return entries[0]
    return entries


def _plist_contents(task: dict, python_executable: str, cli_script_path: str) -> dict:
    stdout_path = str(launchd_logs_dir() / f"{task['id']}.log")
    stderr_path = str(launchd_logs_dir() / f"{task['id']}.err.log")
    return {
        "Label": task_label(task["id"]),
        "ProgramArguments": [python_executable, cli_script_path, "run-id", task["id"]],
        "StartCalendarInterval": _plist_start_calendar_interval(task["schedule"]),
        "StandardOutPath": stdout_path,
        "StandardErrorPath": stderr_path,
        "ProcessType": "Background",
    }


def install_task(task: dict, python_executable: str, cli_script_path: str) -> Path:
    config.ensure_runtime_paths()
    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    launchd_logs_dir().mkdir(parents=True, exist_ok=True)

    plist_path = task_plist_path(task["id"])
    with plist_path.open("wb") as handle:
        plistlib.dump(_plist_contents(task, python_executable, cli_script_path), handle, sort_keys=True)

    _try_run_launchctl(["bootout", launchctl_domain(), str(plist_path)])
    _run_launchctl(["bootstrap", launchctl_domain(), str(plist_path)])
    return plist_path


def remove_task(task_id: str) -> None:
    plist_path = task_plist_path(task_id)
    if plist_path.exists():
        _try_run_launchctl(["bootout", launchctl_domain(), str(plist_path)])
        plist_path.unlink()


def sync_all_tasks(tasks: list[dict], python_executable: str, cli_script_path: str) -> list[str]:
    launch_agents_dir().mkdir(parents=True, exist_ok=True)
    managed_ids = {task["id"] for task in tasks if not bool(task["is_paused"])}
    errors: list[str] = []

    for plist_path in launch_agents_dir().glob(f"{TASK_LABEL_PREFIX}.*.plist"):
        suffix = plist_path.stem.removeprefix(f"{TASK_LABEL_PREFIX}.")
        if suffix not in managed_ids:
            _try_run_launchctl(["bootout", launchctl_domain(), str(plist_path)])
            plist_path.unlink()

    for task in tasks:
        if bool(task["is_paused"]):
            remove_task(task["id"])
        else:
            try:
                install_task(task, python_executable, cli_script_path)
            except Exception as exc:
                remove_task(task["id"])
                errors.append(f"{task['name']}: {exc}")

    return errors
