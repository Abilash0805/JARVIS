"""Tools that let JARVIS schedule, list and cancel its own future tasks."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Callable

from jarvis.scheduler import TaskScheduler
from jarvis.tools.base import Tool, ToolError

_LOG = os.path.expanduser("~/.jarvis/scheduled.log")


def _log_result(name: str, result: str) -> None:
    os.makedirs(os.path.dirname(_LOG), exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {name}\n{result}\n")


def make_scheduler_tools(
    scheduler: TaskScheduler,
    runner: Callable[[str], str],
) -> list[Tool]:
    """``runner`` executes a prompt (typically a fresh agent turn) and returns
    its textual result, which is appended to the scheduled-task log."""

    def schedule_task(prompt: str, when: str, name: str = "") -> str:
        label = name or (prompt[:40] + ("…" if len(prompt) > 40 else ""))

        def callback() -> None:
            _log_result(label, runner(prompt))

        try:
            job = scheduler.add(label, callback, when)
        except ValueError as exc:
            raise ToolError(str(exc))
        scheduler.start()  # idempotent
        repeat = (
            f"every {job.schedule.interval_s:.0f}s"
            if job.schedule.interval_s is not None
            else "once"
        )
        return (
            f"scheduled #{job.id} '{label}' ({repeat}); first run "
            f"{job.next_run:%Y-%m-%d %H:%M:%S}. Results go to {_LOG}"
        )

    def list_tasks() -> str:
        jobs = scheduler.list_jobs()
        if not jobs:
            return "no scheduled tasks"
        return "\n".join(
            f"#{j.id} '{j.name}' next={j.next_run:%H:%M:%S} runs={j.runs}"
            f"{' (repeating)' if j.schedule.interval_s is not None else ''}"
            for j in jobs
        )

    def cancel_task(task_id: int) -> str:
        return "cancelled" if scheduler.cancel(task_id) else "no such task"

    _str = {"type": "string"}
    return [
        Tool(
            "schedule_task",
            "Schedule a task to run later. 'when' accepts 'in 5 minutes', "
            "'every 30 minutes', or 'at 14:30'. The task is a natural-language "
            "prompt JARVIS will execute at that time; results are logged.",
            {"type": "object",
             "properties": {"prompt": _str, "when": _str, "name": _str},
             "required": ["prompt", "when"]},
            schedule_task,
        ),
        Tool(
            "list_tasks", "List currently scheduled tasks.",
            {"type": "object", "properties": {}},
            list_tasks,
        ),
        Tool(
            "cancel_task", "Cancel a scheduled task by its id.",
            {"type": "object",
             "properties": {"task_id": {"type": "integer"}},
             "required": ["task_id"]},
            cancel_task,
        ),
    ]
