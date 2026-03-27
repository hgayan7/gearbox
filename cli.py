import click
import re
from core.manager import TaskManager
from core.db import init_db

DAYS = {
    'sun': 0, 'sunday': 0,
    'mon': 1, 'monday': 1,
    'tue': 2, 'tuesday': 2,
    'wed': 3, 'wednesday': 3,
    'thu': 4, 'thursday': 4,
    'fri': 5, 'friday': 5,
    'sat': 6, 'saturday': 6,
}

def parse_smart_schedule(s: str) -> str:
    s = s.lower().strip()
    if s == "every minute": return "* * * * *"
    if s == "hourly" or s == "every hour": return "0 * * * *"
    if s == "daily" or s == "every day": return "0 0 * * *"
    
    m = re.match(r"every (\d+) minutes?", s)
    if m: return f"*/{m.group(1)} * * * *"
    
    m2 = re.match(r"(?:every\s+)?([a-z]+)(?:\s+at)?\s+(\d{1,2}):(\d{2})", s)
    if m2:
        day = m2.group(1)
        hour = int(m2.group(2))
        minute = int(m2.group(3))
        if day in DAYS:
            return f"{minute} {hour} * * {DAYS[day]}"
            
    return s

@click.group()
def cli():
    """Gearbox: A macOS local automation manager."""
    init_db()
    TaskManager.reconcile_stale_runs()

@cli.command()
@click.argument('name')
@click.argument('schedule')
@click.argument('command')
def add(name, schedule, command):
    """Add a new task.
    Examples:
      gearbox add my-task "*/5 * * * *" "echo hello"
      gearbox add my-task "every 5 minutes" "echo hello"
      gearbox add my-task "daily | monday 10:00" "echo hello"
    """
    parts = [p.strip() for p in schedule.split("|") if p.strip()]
    cron_parts = [parse_smart_schedule(p) for p in parts]
    cron_schedule = " | ".join(cron_parts)
    try:
        TaskManager.add_task(name, cron_schedule, command)
        click.secho(f"Successfully added task '{name}' with schedule '{cron_schedule}'.", fg="green")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            click.secho(f"Task '{name}' already exists. Use rm first, or change name.", fg="red")
        else:
            click.secho(f"Error adding task: {e}", fg="red")

@cli.command()
@click.argument('name')
def rm(name):
    """Remove a task by name."""
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
        
    click.secho(f"{'NAME':<20} | {'SCHEDULE':<30} | {'STATUS':<10} | {'COMMAND'}", bold=True)
    click.secho("-" * 85)
    for t in tasks:
        status = "PAUSED" if t["is_paused"] else "ACTIVE"
        color = "yellow" if t["is_paused"] else "green"
        desc = t.get('schedule_desc') or t['schedule']
        click.secho(f"{t['name']:<20} | {desc:<30} | ", nl=False)
        click.secho(f"{status:<10}", fg=color, nl=False)
        click.secho(f" | {t['command']}")

@cli.command()
@click.argument('name')
def pause(name):
    """Pause a task from running."""
    if TaskManager.set_pause_status(name, True):
        click.secho(f"Task '{name}' is now paused.", fg="yellow")
    else:
        click.secho(f"Task '{name}' not found.", fg="red")

@cli.command()
@click.argument('name')
def resume(name):
    """Resume a paused task."""
    if TaskManager.set_pause_status(name, False):
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
        
    click.secho(f"{'STARTED AT':<28} | {'STATUS':<10} | {'EXIT':<5} | {'ENDED AT'}", bold=True)
    click.secho("-" * 75)
    for r in runs:
        color = "green" if r["status"] == "success" else ("red" if r["status"] == "failed" else "blue")
        exit_code_str = str(r['exit_code']) if r['exit_code'] is not None else '-'
        click.secho(f"{r['started_at']:<28} | ", nl=False)
        click.secho(f"{r['status']:<10}", fg=color, nl=False)
        click.secho(f" | {exit_code_str:<5} | {r['ended_at']}")

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

    TaskManager.execute_task(task["id"], task["command"])
    click.secho(f"Task '{name}' ran successfully.", fg="green")

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

if __name__ == '__main__':
    cli()
