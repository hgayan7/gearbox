from typing import List, Dict, Any, Optional
import uuid
import datetime
import subprocess
import cron_descriptor
import os
import signal
import json
import time
from .db import get_connection

class TaskManager:
    DEFAULT_SHELL = "/bin/zsh"

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    @staticmethod
    def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _normalize_environment_json(environment_json: Optional[str]) -> Optional[str]:
        normalized = TaskManager._normalize_optional_text(environment_json)
        if normalized is None:
            return None

        parsed = json.loads(normalized)
        if not isinstance(parsed, dict):
            raise ValueError("Environment must be a JSON object.")

        clean_env = {str(key): str(value) for key, value in parsed.items()}
        return json.dumps(clean_env, sort_keys=True)

    @staticmethod
    def _describe_schedule(schedule: str) -> str:
        try:
            parts = [p.strip() for p in schedule.split("|") if p.strip()]
            desc_parts = [cron_descriptor.get_description(p) for p in parts]
            return ", and ".join(desc_parts)
        except Exception:
            return schedule

    @staticmethod
    def _display_command(raw_command: Optional[str], working_directory: Optional[str], fallback_command: Optional[str] = None) -> str:
        if raw_command:
            if working_directory:
                return f"cd '{working_directory}' && {raw_command}"
            return raw_command
        return fallback_command or ""

    @staticmethod
    def _parse_environment_json(environment_json: Optional[str]) -> Dict[str, str]:
        if not environment_json:
            return {}

        try:
            parsed = json.loads(environment_json)
        except json.JSONDecodeError:
            return {}

        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}

    @staticmethod
    def _bootstrap_prefix_for_shell(shell_path: str) -> str:
        prefix = "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; "
        shell_name = os.path.basename(shell_path)
        if shell_name == "zsh":
            return prefix + "source ~/.zprofile 2>/dev/null || true; source ~/.zshrc 2>/dev/null || true; "
        if shell_name == "bash":
            return prefix + "source ~/.bash_profile 2>/dev/null || true; source ~/.bashrc 2>/dev/null || true; "
        return prefix

    @staticmethod
    def is_on_ac_power() -> bool:
        try:
            res = subprocess.run(["/usr/bin/pmset", "-g", "batt"], capture_output=True, text=True)
            if "Battery Power" in res.stdout:
                return False
            return True
        except Exception:
            return True

    @staticmethod
    def _command_for_execution(task: Dict[str, Any], fallback_command: Optional[str] = None) -> str:
        raw_command = TaskManager._normalize_optional_text(task.get("raw_command"))
        if raw_command:
            return raw_command
        return fallback_command or task["command"]

    @staticmethod
    def add_task(
        name: str,
        schedule: str,
        command: str,
        raw_command: Optional[str] = None,
        working_directory: Optional[str] = None,
        environment_json: Optional[str] = None,
        shell: Optional[str] = None,
        trigger_type: str = "cron",
        watch_path: Optional[str] = None,
        timeout_seconds: int = 0,
        max_retries: int = 0,
        retry_delay_seconds: int = 10,
        requires_ac_power: bool = False,
        prevent_sleep: bool = False,
        on_success_task_id: Optional[str] = None,
        on_failure_task_id: Optional[str] = None,
    ) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        task_id = str(uuid.uuid4())
        normalized_raw_command = TaskManager._normalize_optional_text(raw_command)
        normalized_working_directory = TaskManager._normalize_optional_text(working_directory)
        normalized_environment_json = TaskManager._normalize_environment_json(environment_json)
        normalized_shell = TaskManager._normalize_optional_text(shell) or TaskManager.DEFAULT_SHELL
        desc = TaskManager._describe_schedule(schedule)
        display_command = TaskManager._display_command(normalized_raw_command, normalized_working_directory, command)
        normalized_watch_path = TaskManager._normalize_optional_text(watch_path)
        normalized_trigger_type = TaskManager._normalize_optional_text(trigger_type) or "cron"

        try:
            cursor.execute('''
                INSERT INTO tasks (
                    id, name, command, schedule, schedule_desc, is_paused,
                    raw_command, working_directory, environment_json, shell,
                    trigger_type, watch_path, timeout_seconds, max_retries,
                    retry_delay_seconds, requires_ac_power, prevent_sleep,
                    on_success_task_id, on_failure_task_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                name,
                display_command,
                schedule,
                desc,
                0,
                normalized_raw_command,
                normalized_working_directory,
                normalized_environment_json,
                normalized_shell,
                normalized_trigger_type,
                normalized_watch_path,
                int(timeout_seconds or 0),
                int(max_retries or 0),
                int(retry_delay_seconds or 10),
                1 if requires_ac_power else 0,
                1 if prevent_sleep else 0,
                TaskManager._normalize_optional_text(on_success_task_id),
                TaskManager._normalize_optional_text(on_failure_task_id),
            ))
            conn.commit()
            return task_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    @staticmethod
    def update_task(
        existing_name: str,
        name: str,
        schedule: str,
        command: str,
        raw_command: Optional[str] = None,
        working_directory: Optional[str] = None,
        environment_json: Optional[str] = None,
        shell: Optional[str] = None,
        trigger_type: str = "cron",
        watch_path: Optional[str] = None,
        timeout_seconds: int = 0,
        max_retries: int = 0,
        retry_delay_seconds: int = 10,
        requires_ac_power: bool = False,
        prevent_sleep: bool = False,
        on_success_task_id: Optional[str] = None,
        on_failure_task_id: Optional[str] = None,
    ) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        normalized_raw_command = TaskManager._normalize_optional_text(raw_command)
        normalized_working_directory = TaskManager._normalize_optional_text(working_directory)
        normalized_environment_json = TaskManager._normalize_environment_json(environment_json)
        normalized_shell = TaskManager._normalize_optional_text(shell) or TaskManager.DEFAULT_SHELL
        desc = TaskManager._describe_schedule(schedule)
        display_command = TaskManager._display_command(normalized_raw_command, normalized_working_directory, command)
        normalized_watch_path = TaskManager._normalize_optional_text(watch_path)
        normalized_trigger_type = TaskManager._normalize_optional_text(trigger_type) or "cron"

        try:
            cursor.execute(
                '''
                UPDATE tasks
                SET name = ?, command = ?, schedule = ?, schedule_desc = ?,
                    raw_command = ?, working_directory = ?, environment_json = ?, shell = ?,
                    trigger_type = ?, watch_path = ?, timeout_seconds = ?, max_retries = ?,
                    retry_delay_seconds = ?, requires_ac_power = ?, prevent_sleep = ?,
                    on_success_task_id = ?, on_failure_task_id = ?
                WHERE name = ?
                ''',
                (
                    name,
                    display_command,
                    schedule,
                    desc,
                    normalized_raw_command,
                    normalized_working_directory,
                    normalized_environment_json,
                    normalized_shell,
                    normalized_trigger_type,
                    normalized_watch_path,
                    int(timeout_seconds or 0),
                    int(max_retries or 0),
                    int(retry_delay_seconds or 10),
                    1 if requires_ac_power else 0,
                    1 if prevent_sleep else 0,
                    TaskManager._normalize_optional_text(on_success_task_id),
                    TaskManager._normalize_optional_text(on_failure_task_id),
                    existing_name,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Task '{existing_name}' not found.")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        task = TaskManager.get_task_by_name(name)
        if task is None:
            raise ValueError(f"Task '{name}' not found after update.")
        return task["id"]

    @staticmethod
    def remove_task(name: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM tasks WHERE name = ?', (name,))
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        finally:
            conn.close()

    @staticmethod
    def get_tasks() -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM tasks')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_task_by_name(name: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM tasks WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def set_pause_status(name: str, is_paused: bool) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE tasks SET is_paused = ? WHERE name = ?', (1 if is_paused else 0, name))
            rows_affected = cursor.rowcount
            conn.commit()
            return rows_affected > 0
        finally:
            conn.close()

    @staticmethod
    def log_run_start(task_id: str, retry_count: int = 0, trigger_source: str = "schedule") -> str:
        conn = get_connection()
        cursor = conn.cursor()
        run_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        try:
            cursor.execute('''
                INSERT INTO runs (id, task_id, status, started_at, retry_count, trigger_source)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (run_id, task_id, "running", now, retry_count, trigger_source))
            conn.commit()
            return run_id
        finally:
            conn.close()

    @staticmethod
    def log_run_end(run_id: str, status: str, exit_code: int, stdout: str = None, stderr: str = None):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        
        # Check current status - don't overwrite "cancelled" with "failed"
        cursor.execute("SELECT status FROM runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        if row and row[0] == "cancelled" and status == "failed":
            status = "cancelled"

        # If stdout/stderr are not provided, try reading from the temp log file
        if stdout is None or stderr is None:
            log_path = os.path.expanduser(f"~/.gearbox/logs/{run_id}.log")
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    stdout = f.read()
                stderr = ""
                try: os.remove(log_path)
                except: pass

        try:
            cursor.execute('''
                UPDATE runs
                SET status = ?, ended_at = ?, exit_code = ?, stdout = ?, stderr = ?
                WHERE id = ?
            ''', (status, now, exit_code, stdout or "", stderr or "", run_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_task_runs(task_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM runs
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT ?
            ''', (task_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def get_latest_run_started_at(task_id: str) -> Optional[str]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                SELECT started_at
                FROM runs
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT 1
                ''',
                (task_id,),
            )
            row = cursor.fetchone()
            return row["started_at"] if row else None
        finally:
            conn.close()
            
    @staticmethod
    def get_recent_runs(limit: int = 10) -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT r.id, r.status, r.started_at, r.ended_at, r.exit_code, t.name as task_name
                FROM runs r
                JOIN tasks t ON r.task_id = t.id
                ORDER BY r.started_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def update_run_pid(run_id: str, pid: int):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE runs SET pid = ? WHERE id = ?', (pid, run_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def has_running_run(task_id: str) -> bool:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM runs WHERE task_id = ? AND status = 'running' LIMIT 1", (task_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    @staticmethod
    def reconcile_stale_runs() -> int:
        """Finalize runs that are still marked running but whose process has already exited."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, pid FROM runs WHERE status = 'running' AND pid IS NOT NULL")
            stale_run_ids = []
            for row in cursor.fetchall():
                if not TaskManager._pid_exists(row["pid"]):
                    stale_run_ids.append(row["id"])
        finally:
            conn.close()

        for run_id in stale_run_ids:
            TaskManager.log_run_end(run_id, "failed", -2)

        return len(stale_run_ids)

    @staticmethod
    def stop_task(task_id: str):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, pid FROM runs WHERE task_id = ? AND status = 'running' AND pid IS NOT NULL", (task_id,))
            for run in cursor.fetchall():
                pid = run["pid"]
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except Exception:
                    pass
                TaskManager.log_run_end(run["id"], "cancelled", -9, "Automation manually stopped by user.", "")
        finally:
            conn.close()

    @staticmethod
    def execute_task(
        task_id: str,
        command: Optional[str] = None,
        retry_count: int = 0,
        trigger_source: str = "schedule",
    ) -> bool:
        if TaskManager.has_running_run(task_id):
            return False

        task = TaskManager.get_task_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found.")

        # Check AC power requirement
        if bool(task.get("requires_ac_power")) and not TaskManager.is_on_ac_power():
            run_id = TaskManager.log_run_start(task_id, retry_count=retry_count, trigger_source=trigger_source)
            TaskManager.log_run_end(
                run_id=run_id,
                status="skipped",
                exit_code=0,
                stdout="Skipped run: task requires AC power, but Mac is currently on battery power.",
                stderr="",
            )
            return False

        run_id = TaskManager.log_run_start(task_id, retry_count=retry_count, trigger_source=trigger_source)
        log_dir = os.path.expanduser("~/.gearbox/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{run_id}.log")
        
        status = "failed"
        exit_code = -1
        timed_out = False

        try:
            shell_path = TaskManager._normalize_optional_text(task.get("shell")) or TaskManager.DEFAULT_SHELL
            working_directory = TaskManager._normalize_optional_text(task.get("working_directory"))
            environment = os.environ.copy()
            environment.update(TaskManager._parse_environment_json(task.get("environment_json")))
            if task.get("trigger_type"):
                environment["GEARBOX_TRIGGER_TYPE"] = str(task["trigger_type"])
            if task.get("watch_path"):
                environment["GEARBOX_WATCH_PATH"] = str(task["watch_path"])
            environment["GEARBOX_RETRY_COUNT"] = str(retry_count)
            environment["GEARBOX_TRIGGER_SOURCE"] = str(trigger_source)

            final_cmd = TaskManager._bootstrap_prefix_for_shell(shell_path) + TaskManager._command_for_execution(task, fallback_command=command)
            
            exec_args = [shell_path, "-c", final_cmd]
            if bool(task.get("prevent_sleep")):
                exec_args = ["/usr/bin/caffeinate", "-dimsu", *exec_args]

            timeout = task.get("timeout_seconds")
            timeout = int(timeout) if timeout and int(timeout) > 0 else None

            with open(log_path, "a") as log_file:
                if retry_count > 0:
                    log_file.write(f"\n--- Gearbox Retry Attempt {retry_count} ---\n")

                process = subprocess.Popen(
                    exec_args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT, # Combine for live streaming simplicity
                    text=True,
                    start_new_session=True,
                    cwd=working_directory or None,
                    env=environment,
                )
                
                TaskManager.update_run_pid(run_id, process.pid)

                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                    # Detect cancellation from signals
                    if exit_code in [-9, -15, 137, 143]:
                        status = "cancelled"
                    else:
                        status = "success" if exit_code == 0 else "failed"
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        time.sleep(0.5)
                        if TaskManager._pid_exists(process.pid):
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:
                        pass
                    log_file.write(f"\n[Gearbox Error] Task execution timed out after {timeout} seconds.\n")
                    status = "failed"
                    exit_code = -124

            TaskManager.log_run_end(
                run_id=run_id,
                status=status,
                exit_code=exit_code,
            )
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"\nInternal Error: {str(e)}\n")
            TaskManager.log_run_end(
                run_id=run_id,
                status="failed",
                exit_code=-1,
            )

        # Retry handling
        max_retries = int(task.get("max_retries") or 0)
        retry_delay = int(task.get("retry_delay_seconds") or 10)

        if status == "failed" and not timed_out and retry_count < max_retries:
            time.sleep(retry_delay)
            return TaskManager.execute_task(
                task_id,
                command=command,
                retry_count=retry_count + 1,
                trigger_source="retry",
            )

        # Workflow chaining
        if status == "success" and task.get("on_success_task_id"):
            successor_id = task["on_success_task_id"]
            if successor_id != task_id:
                TaskManager.execute_task(successor_id, trigger_source="workflow_success")
        elif status == "failed" and task.get("on_failure_task_id"):
            failure_id = task["on_failure_task_id"]
            if failure_id != task_id:
                TaskManager.execute_task(failure_id, trigger_source="workflow_failure")

        return True
