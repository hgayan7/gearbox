from typing import List, Dict, Any, Optional
import uuid
import datetime
import subprocess
import cron_descriptor
import os
import signal
from .db import get_connection

class TaskManager:
    @staticmethod
    def add_task(name: str, schedule: str, command: str) -> str:
        conn = get_connection()
        cursor = conn.cursor()
        task_id = str(uuid.uuid4())
        
        try:
            parts = [p.strip() for p in schedule.split("|") if p.strip()]
            desc_parts = [cron_descriptor.get_description(p) for p in parts]
            desc = ", and ".join(desc_parts)
        except Exception:
            desc = schedule

        try:
            cursor.execute('''
                INSERT INTO tasks (id, name, command, schedule, schedule_desc, is_paused)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, name, command, schedule, desc, 0))
            conn.commit()
            return task_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

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
    def log_run_end(run_id: str, status: str, exit_code: int, stdout: str, stderr: str):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now().isoformat()
        try:
            cursor.execute('''
                UPDATE runs
                SET status = ?, ended_at = ?, exit_code = ?, stdout = ?, stderr = ?
                WHERE id = ?
            ''', (status, now, exit_code, stdout, stderr, run_id))
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
    def execute_task(task_id: str, command: str):
        run_id = TaskManager.log_run_start(task_id)
        try:
            env_setup = "export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; source ~/.zprofile 2>/dev/null || true; source ~/.zshrc 2>/dev/null || true; "
            final_cmd = env_setup + command
            
            process = subprocess.Popen(
                ["/bin/zsh", "-c", final_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True
            )
            
            TaskManager.update_run_pid(run_id, process.pid)
            stdout, stderr = process.communicate()
            
            status = "success" if process.returncode == 0 else "failed"
            TaskManager.log_run_end(
                run_id=run_id,
                status=status,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr
            )
        except Exception as e:
            TaskManager.log_run_end(
                run_id=run_id,
                status="failed",
                exit_code=-1,
                stdout="",
                stderr=str(e)
            )
