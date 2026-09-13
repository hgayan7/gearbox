import click
import os
import re
import sys
import json
import datetime
from pathlib import Path
from core import launchd
from core.manager import TaskManager
from core.db import init_db
from apscheduler.triggers.cron import CronTrigger

DAYS = {
    'sun': 0, 'sunday': 0,
    'mon': 1, 'monday': 1,
    'tue': 2, 'tuesday': 2,
    'wed': 3, 'wednesday': 3,
    'thu': 4, 'thursday': 4,
    'fri': 5, 'friday': 5,
    'sat': 6, 'saturday': 6,
    'weekdays': '1-5',
    'weekday': '1-5',
    'weekends': '0,6',
    'weekend': '0,6',
}

def parse_smart_schedule(s: str) -> str:
    s = s.lower().strip()
    if s == "hourly" or s == "every hour": return "0 * * * *"
    if s == "daily" or s == "every day": return "0 0 * * *"

    every_minutes = re.match(r"every\s+(\d+)\s+minutes?$", s)
    if every_minutes:
        minutes = int(every_minutes.group(1))
        if minutes <= 0 or 60 % minutes != 0:
            raise ValueError("Minute intervals must divide evenly into one hour.")
        return " | ".join(f"{minute} * * * *" for minute in range(0, 60, minutes))
    
    m2 = re.match(r"(?:every\s+)?([a-z]+)(?:\s+at)?\s+(\d{1,2}):(\d{2})", s)
    if m2:
        day = m2.group(1)
        hour = int(m2.group(2))
        minute = int(m2.group(3))
        if day in DAYS:
            day_value = DAYS[day]
            return f"{minute} {hour} * * {day_value}"
            
    return s


def normalize_schedule_input(schedule: str) -> str:
    parts = [p.strip() for p in schedule.split("|") if p.strip()]
    if not parts:
        raise ValueError("Schedule is empty.")
    return " | ".join(parse_smart_schedule(part) for part in parts)


def schedule_preview_payload(schedule: str, limit: int = 3) -> dict:
    normalized_schedule = normalize_schedule_input(schedule)
    launchd.cron_schedule_to_calendar_entries(normalized_schedule)

    timezone = datetime.datetime.now().astimezone().tzinfo
    if timezone is None:
        raise ValueError("Unable to determine local timezone.")

    now = datetime.datetime.now(timezone)
    upcoming: list[datetime.datetime] = []
    for cron_expr in [part.strip() for part in normalized_schedule.split("|") if part.strip()]:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=timezone)
        previous_fire_time = None
        cursor = now
        for _ in range(limit):
            next_fire_time = trigger.get_next_fire_time(previous_fire_time, cursor)
            if next_fire_time is None:
                break
            upcoming.append(next_fire_time)
            previous_fire_time = next_fire_time
            cursor = next_fire_time

    deduped = sorted({fire_time.isoformat(): fire_time for fire_time in upcoming}.values())[:limit]
    return {
        "normalized_schedule": normalized_schedule,
        "description": TaskManager._describe_schedule(normalized_schedule),
        "timezone": str(timezone),
        "next_runs": [fire_time.isoformat() for fire_time in deduped],
    }

@click.group()
def cli():
    """Gearbox: A macOS local automation manager."""
    init_db()
    TaskManager.reconcile_stale_runs()


def _runner_context() -> tuple[str, str]:
    return sys.executable, os.path.realpath(__file__)

@cli.command()
@click.argument('name')
@click.argument('schedule')
@click.argument('command')
@click.option('--raw-command', default=None, help='Shell command to execute before any working-directory handling.')
@click.option('--working-directory', default=None, help='Working directory for the task.')
@click.option('--env-json', default=None, help='JSON object of environment variables for the task.')
@click.option('--shell', default=None, help='Shell used to execute the task, e.g. /bin/zsh.')
@click.option('--trigger-type', default='cron', help='Trigger type: cron, file_watch, or system_event.')
@click.option('--watch-path', default=None, help='Directory path to watch if trigger type is file_watch.')
@click.option('--timeout', default=0, type=int, help='Timeout in seconds (0 = unlimited).')
@click.option('--max-retries', default=0, type=int, help='Maximum retry attempts on failure.')
@click.option('--retry-delay', default=10, type=int, help='Delay in seconds between retries.')
@click.option('--requires-ac/--no-requires-ac', default=False, help='Only execute when Mac is on AC power.')
@click.option('--prevent-sleep/--no-prevent-sleep', default=False, help='Prevent system sleep during execution (caffeinate).')
@click.option('--on-success', default=None, help='Task name or ID to trigger upon successful completion.')
@click.option('--on-failure', default=None, help='Task name or ID to trigger upon failure after all retries.')
def add(name, schedule, command, raw_command, working_directory, env_json, shell,
        trigger_type, watch_path, timeout, max_retries, retry_delay, requires_ac, prevent_sleep,
        on_success, on_failure):
    """Add a new task.
    Examples:
      gearbox add my-task "daily | monday 10:00" "echo hello"
      gearbox add watch-downloads "watch" "python process.py" --trigger-type file_watch --watch-path ~/Downloads
    """
    task_id = None
    try:
        if trigger_type == "file_watch":
            cron_schedule = schedule or "file_watch"
        else:
            cron_schedule = normalize_schedule_input(schedule)
            launchd.cron_schedule_to_calendar_entries(cron_schedule)

        succ_id = None
        if on_success:
            s_task = TaskManager.get_task_by_name(on_success) or TaskManager.get_task_by_id(on_success)
            succ_id = s_task["id"] if s_task else on_success

        fail_id = None
        if on_failure:
            f_task = TaskManager.get_task_by_name(on_failure) or TaskManager.get_task_by_id(on_failure)
            fail_id = f_task["id"] if f_task else on_failure

        task_id = TaskManager.add_task(
            name,
            cron_schedule,
            command,
            raw_command=raw_command,
            working_directory=working_directory,
            environment_json=env_json,
            shell=shell,
            trigger_type=trigger_type,
            watch_path=watch_path,
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay,
            requires_ac_power=requires_ac,
            prevent_sleep=prevent_sleep,
            on_success_task_id=succ_id,
            on_failure_task_id=fail_id,
        )
        task = TaskManager.get_task_by_id(task_id)
        python_executable, cli_script_path = _runner_context()
        launchd.install_task(task, python_executable, cli_script_path)
        click.secho(f"Successfully added task '{name}' (trigger: {trigger_type}).", fg="green")
    except Exception as e:
        if task_id is not None:
            launchd.remove_task(task_id)
            TaskManager.remove_task(name)
        if "UNIQUE constraint failed" in str(e):
            raise click.ClickException(f"Task '{name}' already exists. Use rm first, or change name.")
        else:
            raise click.ClickException(f"Error adding task: {e}")


@cli.command()
@click.argument('existing_name')
@click.argument('name')
@click.argument('schedule')
@click.argument('command')
@click.option('--raw-command', default=None, help='Shell command to execute before any working-directory handling.')
@click.option('--working-directory', default=None, help='Working directory for the task.')
@click.option('--env-json', default=None, help='JSON object of environment variables for the task.')
@click.option('--shell', default=None, help='Shell used to execute the task, e.g. /bin/zsh.')
@click.option('--trigger-type', default='cron', help='Trigger type: cron, file_watch, or system_event.')
@click.option('--watch-path', default=None, help='Directory path to watch if trigger type is file_watch.')
@click.option('--timeout', default=0, type=int, help='Timeout in seconds (0 = unlimited).')
@click.option('--max-retries', default=0, type=int, help='Maximum retry attempts on failure.')
@click.option('--retry-delay', default=10, type=int, help='Delay in seconds between retries.')
@click.option('--requires-ac/--no-requires-ac', default=False, help='Only execute when Mac is on AC power.')
@click.option('--prevent-sleep/--no-prevent-sleep', default=False, help='Prevent system sleep during execution (caffeinate).')
@click.option('--on-success', default=None, help='Task name or ID to trigger upon successful completion.')
@click.option('--on-failure', default=None, help='Task name or ID to trigger upon failure after all retries.')
def update(existing_name, name, schedule, command, raw_command, working_directory, env_json, shell,
           trigger_type, watch_path, timeout, max_retries, retry_delay, requires_ac, prevent_sleep,
           on_success, on_failure):
    """Update an existing task by name."""
    existing_task = TaskManager.get_task_by_name(existing_name)
    if not existing_task:
        click.secho(f"Task '{existing_name}' not found.", fg="red")
        return

    try:
        if trigger_type == "file_watch":
            cron_schedule = schedule or "file_watch"
        else:
            cron_schedule = normalize_schedule_input(schedule)
            launchd.cron_schedule_to_calendar_entries(cron_schedule)

        succ_id = None
        if on_success:
            s_task = TaskManager.get_task_by_name(on_success) or TaskManager.get_task_by_id(on_success)
            succ_id = s_task["id"] if s_task else on_success

        fail_id = None
        if on_failure:
            f_task = TaskManager.get_task_by_name(on_failure) or TaskManager.get_task_by_id(on_failure)
            fail_id = f_task["id"] if f_task else on_failure

        task_id = TaskManager.update_task(
            existing_name,
            name,
            cron_schedule,
            command,
            raw_command=raw_command,
            working_directory=working_directory,
            environment_json=env_json,
            shell=shell,
            trigger_type=trigger_type,
            watch_path=watch_path,
            timeout_seconds=timeout,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay,
            requires_ac_power=requires_ac,
            prevent_sleep=prevent_sleep,
            on_success_task_id=succ_id,
            on_failure_task_id=fail_id,
        )
        updated_task = TaskManager.get_task_by_id(task_id)
        python_executable, cli_script_path = _runner_context()
        if updated_task and not bool(updated_task["is_paused"]):
            launchd.install_task(updated_task, python_executable, cli_script_path)
        elif updated_task:
            launchd.remove_task(updated_task["id"])
        click.secho(f"Task '{existing_name}' updated.", fg="green")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise click.ClickException(f"Task '{name}' already exists. Choose a different name.")
        else:
            raise click.ClickException(f"Error updating task: {e}")

@cli.command()
@click.argument('name')
def rm(name):
    """Remove a task by name."""
    task = TaskManager.get_task_by_name(name)
    if task:
        launchd.remove_task(task["id"])
    if TaskManager.remove_task(name):
        click.secho(f"Task '{name}' removed.", fg="green")
    else:
        click.secho(f"Task '{name}' not found.", fg="yellow")

@cli.command()
def ls():
    """List all scheduled tasks."""
    tasks = TaskManager.get_tasks()
    if not tasks:
        click.secho("No tasks found.", fg="yellow")
        return
        
    click.secho(f"{'NAME':<20} | {'TRIGGER':<24} | {'STATUS':<10} | {'FLAGS':<14} | {'COMMAND'}", bold=True)
    click.secho("-" * 95)
    for t in tasks:
        status = "PAUSED" if t["is_paused"] else "ACTIVE"
        color = "yellow" if t["is_paused"] else "green"
        if t.get("trigger_type") == "file_watch":
            desc = f"Watch: {t.get('watch_path') or '-'}"
        else:
            desc = t.get('schedule_desc') or t['schedule']

        flags = []
        if t.get("timeout_seconds"):
            flags.append(f"{t['timeout_seconds']}s")
        if t.get("requires_ac_power"):
            flags.append("AC")
        if t.get("prevent_sleep"):
            flags.append("caff")
        if t.get("max_retries"):
            flags.append(f"retry:{t['max_retries']}")
        flag_str = ",".join(flags) if flags else "-"

        click.secho(f"{t['name']:<20} | {desc[:24]:<24} | ", nl=False)
        click.secho(f"{status:<10}", fg=color, nl=False)
        click.secho(f" | {flag_str:<14} | {t['command']}")

@cli.command()
@click.argument('name')
def pause(name):
    """Pause a task from running."""
    if TaskManager.set_pause_status(name, True):
        task = TaskManager.get_task_by_name(name)
        if task:
            launchd.remove_task(task["id"])
        click.secho(f"Task '{name}' is now paused.", fg="yellow")
    else:
        click.secho(f"Task '{name}' not found.", fg="red")

@cli.command()
@click.argument('name')
def resume(name):
    """Resume a paused task."""
    if TaskManager.set_pause_status(name, False):
        task = TaskManager.get_task_by_name(name)
        if task:
            python_executable, cli_script_path = _runner_context()
            launchd.install_task(task, python_executable, cli_script_path)
        click.secho(f"Task '{name}' resumed.", fg="green")
    else:
        click.secho(f"Task '{name}' not found.", fg="red")

@cli.command()
@click.argument('name')
@click.option('--limit', default=10, help='Number of recent runs to show')
def history(name, limit):
    """View execution history for a task."""
    task = TaskManager.get_task_by_name(name)
    if not task:
        click.secho(f"Task '{name}' not found.", fg="red")
        return
        
    runs = TaskManager.get_task_runs(task["id"], limit)
    if not runs:
        click.secho(f"No run history for '{name}'.", fg="yellow")
        return
        
    click.secho(f"{'STARTED AT':<26} | {'STATUS':<10} | {'EXIT':<5} | {'SOURCE':<10} | {'ENDED AT'}", bold=True)
    click.secho("-" * 80)
    for r in runs:
        color = "green" if r["status"] == "success" else ("red" if r["status"] == "failed" else "blue")
        exit_code_str = str(r['exit_code']) if r['exit_code'] is not None else '-'
        source_str = str(r.get('trigger_source') or 'schedule')
        if r.get("retry_count"):
            source_str += f" (r{r['retry_count']})"
        click.secho(f"{r['started_at']:<26} | ", nl=False)
        click.secho(f"{r['status']:<10}", fg=color, nl=False)
        click.secho(f" | {exit_code_str:<5} | {source_str:<10} | {r['ended_at']}")

@cli.command()
@click.argument('name')
def logs(name):
    """View stdout and stderr of the most recent run for a task."""
    task = TaskManager.get_task_by_name(name)
    if not task:
        click.secho(f"Task '{name}' not found.", fg="red")
        return
        
    runs = TaskManager.get_task_runs(task["id"], limit=1)
    if not runs:
        click.secho(f"No run history for '{name}'.", fg="yellow")
        return
        
    latest_run = runs[0]
    click.secho(f"--- Task: {name} | Status: {latest_run['status']} ---", bold=True, fg="blue")
    click.secho(f"Started : {latest_run['started_at']}")
    click.secho(f"Ended   : {latest_run['ended_at']}")
    click.secho(f"Exit    : {latest_run['exit_code']}")
    
    click.secho("\n[STDOUT]", bold=True, fg="green")
    click.echo(latest_run["stdout"] or "(empty)")
    
    click.secho("\n[STDERR]", bold=True, fg="red")
    click.echo(latest_run["stderr"] or "(empty)")

@cli.command()
@click.argument('name')
@click.option('--bg', is_flag=True)
def run(name, bg):
    """Run a task immediately."""
    task = TaskManager.get_task_by_name(name)
    if not task:
        click.secho(f"Task '{name}' not found.", fg="red")
        return
        
    if bg:
        import subprocess
        import sys
        import os
        script_path = os.path.realpath(__file__)
        with open(os.devnull, "r") as devnull_in, open(os.devnull, "a") as devnull_out:
            subprocess.Popen(
                [sys.executable, script_path, "run", name],
                stdin=devnull_in,
                stdout=devnull_out,
                stderr=devnull_out,
                close_fds=True,
                start_new_session=True,
            )
        return

    if TaskManager.execute_task(task["id"]):
        click.secho(f"Task '{name}' ran successfully.", fg="green")
    else:
        click.secho(f"Task '{name}' is already running. Skipped duplicate launch.", fg="yellow")


@cli.command("run-id", hidden=True)
@click.argument("task_id")
def run_id(task_id):
    """Run a task by internal id."""
    task = TaskManager.get_task_by_id(task_id)
    if not task:
        raise click.ClickException(f"Task id '{task_id}' not found.")

    TaskManager.execute_task(task["id"])


@cli.command("sync-schedules", hidden=True)
def sync_schedules():
    """Rebuild launchd schedules for all tasks."""
    python_executable, cli_script_path = _runner_context()
    errors = launchd.sync_all_tasks(TaskManager.get_tasks(), python_executable, cli_script_path)
    if errors:
        click.secho("Schedules synced with warnings:", fg="yellow")
        for error in errors:
            click.secho(f"- {error}", fg="yellow")
    else:
        click.secho("Schedules synced.", fg="green")

@cli.command()
@click.argument('name')
def stop(name):
    """Stop an actively running task."""
    task = TaskManager.get_task_by_name(name)
    if not task:
        click.secho(f"Task '{name}' not found.", fg="red")
        return
        
    TaskManager.stop_task(task["id"])
    click.secho(f"Sent stop signal to active runs for '{name}'.", fg="green")


@cli.command("preview-schedule", hidden=True)
@click.argument("schedule")
def preview_schedule(schedule):
    """Return normalized schedule information as JSON."""
    try:
        click.echo(json.dumps(schedule_preview_payload(schedule)))
    except Exception as e:
        raise click.ClickException(str(e))


if __name__ == '__main__':
    cli()
