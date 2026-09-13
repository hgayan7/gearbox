from typing import List, Dict, Any, Optional, Tuple
import os
import sys
import json
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from .manager import TaskManager
from . import launchd


def _runner_context() -> Tuple[str, str]:
    python_bin = sys.executable
    cli_path = str(Path(__file__).parent.parent / "cli.py")
    return python_bin, cli_path


def export_spec(tasks: Optional[List[Dict[str, Any]]] = None, format_type: str = "yaml") -> str:
    """Export current or provided tasks to a declarative YAML or JSON specification string."""
    if tasks is None:
        tasks = TaskManager.get_tasks()

    exported_tasks = []
    # Build a lookup of ID -> name for pipeline links
    id_to_name = {t["id"]: t["name"] for t in tasks if t.get("id") and t.get("name")}

    for t in sorted(tasks, key=lambda x: x.get("name", "")):
        item: Dict[str, Any] = {
            "name": t.get("name"),
            "command": t.get("raw_command") or t.get("command"),
        }

        trigger_type = t.get("trigger_type") or "cron"
        if trigger_type == "file_watch":
            item["trigger"] = {
                "type": "file_watch",
                "watch_path": t.get("watch_path") or "",
            }
        else:
            item["trigger"] = {
                "type": "cron",
                "schedule": t.get("schedule") or "* * * * *",
            }

        # Optional execution configurations
        if t.get("working_directory"):
            item["working_directory"] = t["working_directory"]
        if t.get("shell") and t["shell"] != TaskManager.DEFAULT_SHELL:
            item["shell"] = t["shell"]
        if t.get("environment_json"):
            try:
                env_dict = json.loads(t["environment_json"])
                if env_dict:
                    item["environment"] = env_dict
            except Exception:
                pass

        # Safety options
        safety: Dict[str, Any] = {}
        if t.get("timeout_seconds"):
            safety["timeout_seconds"] = int(t["timeout_seconds"])
        if t.get("requires_ac_power"):
            safety["requires_ac_power"] = bool(t["requires_ac_power"])
        if t.get("prevent_sleep"):
            safety["prevent_sleep"] = bool(t["prevent_sleep"])
        if safety:
            item["safety"] = safety

        # Resilience / Retries
        if t.get("max_retries"):
            item["retries"] = {
                "max_retries": int(t["max_retries"]),
                "retry_delay_seconds": int(t.get("retry_delay_seconds") or 10),
            }

        # Pipeline links (map IDs to human-readable task names)
        pipeline: Dict[str, Any] = {}
        if t.get("on_success_task_id"):
            succ_id = t["on_success_task_id"]
            pipeline["on_success"] = id_to_name.get(succ_id, succ_id)
        if t.get("on_failure_task_id"):
            fail_id = t["on_failure_task_id"]
            pipeline["on_failure"] = id_to_name.get(fail_id, fail_id)
        if pipeline:
            item["pipeline"] = pipeline

        if bool(t.get("is_paused")):
            item["is_paused"] = True

        exported_tasks.append(item)

    spec = {
        "version": 1,
        "tasks": exported_tasks,
    }

    if format_type.lower() == "json" or not HAS_YAML:
        return json.dumps(spec, indent=2)
    else:
        return yaml.dump(spec, sort_keys=False, default_flow_style=False)


def load_spec(content: str, format_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse and normalize tasks from a YAML or JSON specification string."""
    data = None
    if format_type == "json" or content.strip().startswith("{"):
        try:
            data = json.loads(content)
        except Exception as e:
            if not HAS_YAML:
                raise ValueError(f"Failed to parse JSON specification: {e}")

    if data is None:
        if not HAS_YAML:
            raise RuntimeError("PyYAML is not installed. Please run  to parse YAML specifications.")
        try:
            data = yaml.safe_load(content)
        except Exception as e:
            raise ValueError(f"Failed to parse YAML specification: {e}")

    if not isinstance(data, dict):
        raise ValueError("Specification must be a dictionary with top-level 'tasks'.")

    raw_tasks = data.get("tasks", [])
    if not isinstance(raw_tasks, list):
        raise ValueError("Specification 'tasks' must be a list of task objects.")

    normalized_tasks = []
    for idx, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            raise ValueError(f"Task item #{idx + 1} is not a valid dictionary.")

        name = raw.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"Task item #{idx + 1} is missing a valid 'name'.")

        command = raw.get("command") or raw.get("raw_command")
        if not command or not isinstance(command, str):
            raise ValueError(f"Task '{name}' is missing a valid 'command'.")

        # Extract trigger
        trigger = raw.get("trigger", {})
        if isinstance(trigger, str):
            # Shorthand trigger e.g. trigger: "0 * * * *"
            trigger_type = "cron"
            schedule = trigger
            watch_path = None
        elif isinstance(trigger, dict):
            trigger_type = trigger.get("type") or raw.get("trigger_type") or "cron"
            schedule = trigger.get("schedule") or trigger.get("cron") or raw.get("schedule") or "0 * * * *"
            watch_path = trigger.get("watch_path") or raw.get("watch_path")
        else:
            trigger_type = raw.get("trigger_type") or "cron"
            schedule = raw.get("schedule") or "0 * * * *"
            watch_path = raw.get("watch_path")

        # Extract safety
        safety = raw.get("safety", {})
        timeout_seconds = safety.get("timeout_seconds") or raw.get("timeout_seconds") or raw.get("timeout") or 0
        requires_ac_power = safety.get("requires_ac_power", raw.get("requires_ac_power", False))
        prevent_sleep = safety.get("prevent_sleep", raw.get("prevent_sleep", False))

        # Extract retries
        retries = raw.get("retries", {})
        max_retries = retries.get("max_retries") or raw.get("max_retries") or 0
        retry_delay = retries.get("retry_delay_seconds") or retries.get("retry_delay") or raw.get("retry_delay_seconds") or 10

        # Extract pipeline
        pipeline = raw.get("pipeline", {})
        on_success = pipeline.get("on_success") or raw.get("on_success") or raw.get("on_success_task_id")
        on_failure = pipeline.get("on_failure") or raw.get("on_failure") or raw.get("on_failure_task_id")

        # Environment
        env = raw.get("environment") or raw.get("env")
        if isinstance(env, dict):
            env_json = json.dumps(env)
        elif isinstance(env, str):
            env_json = env
        else:
            env_json = raw.get("environment_json")

        normalized = {
            "name": name.strip(),
            "command": command.strip(),
            "raw_command": command.strip(),
            "trigger_type": trigger_type,
            "schedule": schedule,
            "watch_path": watch_path,
            "working_directory": raw.get("working_directory"),
            "shell": raw.get("shell"),
            "environment_json": env_json,
            "timeout_seconds": int(timeout_seconds),
            "max_retries": int(max_retries),
            "retry_delay_seconds": int(retry_delay),
            "requires_ac_power": bool(requires_ac_power),
            "prevent_sleep": bool(prevent_sleep),
            "on_success": on_success,
            "on_failure": on_failure,
            "is_paused": bool(raw.get("is_paused", False)),
        }
        normalized_tasks.append(normalized)

    return normalized_tasks


def apply_spec(spec_tasks: List[Dict[str, Any]], prune: bool = False) -> Dict[str, Any]:
    """Idempotently apply normalized task specifications to the database and sync launchd."""
    existing_tasks = {t["name"]: t for t in TaskManager.get_tasks()}
    spec_names = {t["name"] for t in spec_tasks}

    results = {
        "created": [],
        "updated": [],
        "pruned": [],
        "unchanged": [],
    }

    name_to_id = {}
    for task_spec in spec_tasks:
        name = task_spec["name"]
        sched = task_spec["schedule"]
        cmd = task_spec["command"]

        if name in existing_tasks:
            task_id = TaskManager.update_task(
                existing_name=name,
                name=name,
                schedule=sched,
                command=cmd,
                raw_command=task_spec.get("raw_command"),
                working_directory=task_spec.get("working_directory"),
                environment_json=task_spec.get("environment_json"),
                shell=task_spec.get("shell"),
                trigger_type=task_spec.get("trigger_type") or "cron",
                watch_path=task_spec.get("watch_path"),
                timeout_seconds=task_spec.get("timeout_seconds") or 0,
                max_retries=task_spec.get("max_retries") or 0,
                retry_delay_seconds=task_spec.get("retry_delay_seconds") or 10,
                requires_ac_power=task_spec.get("requires_ac_power", False),
                prevent_sleep=task_spec.get("prevent_sleep", False),
            )
            TaskManager.set_pause_status(name, task_spec.get("is_paused", False))
            name_to_id[name] = task_id
            results["updated"].append(name)
        else:
            task_id = TaskManager.add_task(
                name=name,
                schedule=sched,
                command=cmd,
                raw_command=task_spec.get("raw_command"),
                working_directory=task_spec.get("working_directory"),
                environment_json=task_spec.get("environment_json"),
                shell=task_spec.get("shell"),
                trigger_type=task_spec.get("trigger_type") or "cron",
                watch_path=task_spec.get("watch_path"),
                timeout_seconds=task_spec.get("timeout_seconds") or 0,
                max_retries=task_spec.get("max_retries") or 0,
                retry_delay_seconds=task_spec.get("retry_delay_seconds") or 10,
                requires_ac_power=task_spec.get("requires_ac_power", False),
                prevent_sleep=task_spec.get("prevent_sleep", False),
            )
            if task_spec.get("is_paused"):
                TaskManager.set_pause_status(name, True)
            name_to_id[name] = task_id
            results["created"].append(name)

    for task_spec in spec_tasks:
        name = task_spec["name"]
        on_success = task_spec.get("on_success")
        on_failure = task_spec.get("on_failure")

        succ_id = None
        if on_success:
            succ_id = name_to_id.get(on_success) or (TaskManager.get_task_by_name(on_success) or {}).get("id") or on_success

        fail_id = None
        if on_failure:
            fail_id = name_to_id.get(on_failure) or (TaskManager.get_task_by_name(on_failure) or {}).get("id") or on_failure

        if succ_id or fail_id:
            TaskManager.update_task(
                existing_name=name,
                name=name,
                schedule=task_spec["schedule"],
                command=task_spec["command"],
                raw_command=task_spec.get("raw_command"),
                working_directory=task_spec.get("working_directory"),
                environment_json=task_spec.get("environment_json"),
                shell=task_spec.get("shell"),
                trigger_type=task_spec.get("trigger_type") or "cron",
                watch_path=task_spec.get("watch_path"),
                timeout_seconds=task_spec.get("timeout_seconds") or 0,
                max_retries=task_spec.get("max_retries") or 0,
                retry_delay_seconds=task_spec.get("retry_delay_seconds") or 10,
                requires_ac_power=task_spec.get("requires_ac_power", False),
                prevent_sleep=task_spec.get("prevent_sleep", False),
                on_success_task_id=succ_id,
                on_failure_task_id=fail_id,
            )

    if prune:
        for existing_name in existing_tasks:
            if existing_name not in spec_names:
                task = existing_tasks[existing_name]
                launchd.remove_task(task["id"])
                TaskManager.remove_task(existing_name)
                results["pruned"].append(existing_name)

    python_bin, cli_path = _runner_context()
    current_tasks = TaskManager.get_tasks()
    launchd.sync_all_tasks(current_tasks, python_bin, cli_path)

    return results
