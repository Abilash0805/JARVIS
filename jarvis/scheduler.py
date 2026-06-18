"""A tiny, dependency-free task scheduler.

Runs callbacks once (``in 5 minutes`` / ``at 14:30``) or repeatedly
(``every 10 minutes``) on a background daemon thread. The time-spec parser is
pure and unit-tested; the threading is a thin layer on top.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import count
from typing import Callable, Optional

from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.scheduler")

_REL = re.compile(r"in\s+(\d+)\s*(s|sec|secs|seconds|m|min|mins|minutes|h|hour|hours)")
_EVERY = re.compile(r"every\s+(\d+)\s*(s|sec|secs|seconds|m|min|mins|minutes|h|hour|hours)")
_AT = re.compile(r"at\s+(\d{1,2}):(\d{2})")

_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minutes": 60,
    "h": 3600, "hour": 3600, "hours": 3600,
}


@dataclass
class Schedule:
    """Resolved schedule: when to first run, and an optional repeat interval."""

    run_at: datetime
    interval_s: Optional[float] = None  # None => one-shot


def parse_when(spec: str, *, now: Optional[datetime] = None) -> Schedule:
    """Parse a natural-ish schedule string into a :class:`Schedule`.

    Supported: ``in 5 minutes``, ``every 30 seconds``, ``at 14:30``.
    Raises ``ValueError`` on anything it doesn't understand.
    """
    now = now or datetime.now()
    text = spec.strip().lower()

    m = _EVERY.search(text)
    if m:
        secs = int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
        return Schedule(run_at=now + timedelta(seconds=secs), interval_s=float(secs))

    m = _REL.search(text)
    if m:
        secs = int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
        return Schedule(run_at=now + timedelta(seconds=secs))

    m = _AT.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError(f"invalid time: {spec!r}")
        run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if run_at <= now:  # already passed today => tomorrow
            run_at += timedelta(days=1)
        return Schedule(run_at=run_at)

    raise ValueError(
        f"could not parse schedule {spec!r}; try 'in 5 minutes', "
        "'every 30 seconds', or 'at 14:30'"
    )


@dataclass
class Job:
    id: int
    name: str
    callback: Callable[[], None]
    schedule: Schedule
    next_run: datetime
    active: bool = True
    runs: int = 0

    def is_due(self, now: datetime) -> bool:
        return self.active and now >= self.next_run


@dataclass
class TaskScheduler:
    """Background scheduler. Call :meth:`start` to spin up the worker thread."""

    poll_interval: float = 1.0
    _jobs: dict[int, Job] = field(default_factory=dict)
    _ids: "count[int]" = field(default_factory=lambda: count(1))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread: Optional[threading.Thread] = None
    _stop: threading.Event = field(default_factory=threading.Event)

    def add(self, name: str, callback: Callable[[], None], when: str) -> Job:
        sched = parse_when(when)
        with self._lock:
            job = Job(
                id=next(self._ids),
                name=name,
                callback=callback,
                schedule=sched,
                next_run=sched.run_at,
            )
            self._jobs[job.id] = job
        logger.info("scheduled #%d %r for %s", job.id, name, job.next_run)
        return job

    def cancel(self, job_id: int) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            job.active = False
            del self._jobs[job_id]
            return True

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-sched")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            for job in self.list_jobs():
                if not job.is_due(now):
                    continue
                self._fire(job, now)
            self._stop.wait(self.poll_interval)

    def _fire(self, job: Job, now: datetime) -> None:
        try:
            job.callback()
        except Exception as exc:  # noqa: BLE001 - never kill the scheduler
            logger.warning("job #%d %r raised: %s", job.id, job.name, exc)
        job.runs += 1
        if job.schedule.interval_s is not None:
            job.next_run = now + timedelta(seconds=job.schedule.interval_s)
        else:
            self.cancel(job.id)
