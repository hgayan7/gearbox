from typing import List, Dict, Any, Optional
import uuid
import datetime
import subprocess
import cron_descriptor
import os
import signal
import json
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

        try:
            cursor.execute('''
                INSERT INTO tasks (
                    id, name, command, schedule, schedule_desc, is_paused,
                    raw_command, working_directory, environment_json, shell
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    ) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        normalized_raw_command = TaskManager._normalize_optional_text(raw_command)
        normalized_working_directory = TaskManager._normalize_optional_text(working_directory)
        normalized_environment_json = TaskManager._normalize_environment_json(environment_json)
        normalized_shell = TaskManager._normalize_optional_text(shell) or TaskManager.DEFAULT_SHELL
        desc = TaskManager._describe_schedule(schedule)
        display_command = TaskManager._display_command(normalized_raw_command, normalized_working_directory, command)

        try:
            cursor.execute(
                '''
                UPDATE tasks
                SET name = ?, command = ?, schedule = ?, schedule_desc = ?,
                    raw_command = ?, working_directory = ?, environment_json = ?, shell = ?
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
    def log_run_start(task_id: str) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        run_id = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        try:
            cursor.execute('''
                INSERT INTO runs (id, task_id, status, started_at)
                VALUES (?, ?, ?, ?)
            ''', (run_id, task_id, "running", now))
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
    def execute_task(task_id: str, command: Optional[str] = None) -> bool:
        if TaskManager.has_running_run(task_id):
            return False

        task = TaskManager.get_task_by_id(task_id)
        if task is None:
            raise ValueError(f"Task '{task_id}' not found.")

        run_id = TaskManager.log_run_start(task_id)
        log_dir = os.path.expanduser("~/.gearbox/logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{run_id}.log")
        
        try:
            shell_path = TaskManager._normalize_optional_text(task.get("shell")) or TaskManager.DEFAULT_SHELL
            working_directory = TaskManager._normalize_optional_text(task.get("working_directory"))
            environment = os.environ.copy()
            environment.update(TaskManager._parse_environment_json(task.get("environment_json")))

            final_cmd = TaskManager._bootstrap_prefix_for_shell(shell_path) + TaskManager._command_for_execution(task, fallback_command=command)
            
            with open(log_path, "w") as log_file:
                process = subprocess.Popen(
                    [shell_path, "-c", final_cmd],
                    stdout=log_file,
                    stderr=subprocess.STDOUT, # Combine for live streaming simplicity
                    text=True,
                    start_new_session=True,
                    cwd=working_directory or None,
                    env=environment,
                )
                
                TaskManager.update_run_pid(run_id, process.pid)
                process.wait()
            
            # Detect cancellation from signals
            if process.returncode in [-9, -15, 137, 143]:
                status = "cancelled"
            else:
                status = "success" if process.returncode == 0 else "failed"
                
            TaskManager.log_run_end(
                run_id=run_id,
                status=status,
                exit_code=process.returncode
            )
        except Exception as e:
            with open(log_path, "a") as f:
                f.write(f"\nInternal Error: {str(e)}\n")
            TaskManager.log_run_end(
                run_id=run_id,
                status="failed",
                exit_code=-1
            )
        return True
