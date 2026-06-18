"""Tests for the schedule parser and the scheduler firing logic."""

import threading
import time
from datetime import datetime

import pytest

from jarvis.scheduler import Schedule, TaskScheduler, parse_when


def test_parse_relative():
    now = datetime(2030, 1, 1, 12, 0, 0)
    s = parse_when("in 5 minutes", now=now)
    assert s.interval_s is None
    assert (s.run_at - now).total_seconds() == 300


def test_parse_every_sets_interval():
    now = datetime(2030, 1, 1, 12, 0, 0)
    s = parse_when("every 30 seconds", now=now)
    assert s.interval_s == 30
    assert (s.run_at - now).total_seconds() == 30


def test_parse_at_rolls_to_tomorrow_if_passed():
    now = datetime(2030, 1, 1, 15, 0, 0)
    s = parse_when("at 09:00", now=now)
    assert s.run_at.day == 2 and s.run_at.hour == 9


def test_parse_at_today_if_future():
    now = datetime(2030, 1, 1, 8, 0, 0)
    s = parse_when("at 09:30", now=now)
    assert s.run_at.day == 1 and (s.run_at.hour, s.run_at.minute) == (9, 30)


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        parse_when("whenever I feel like it")


def test_scheduler_fires_once():
    sched = TaskScheduler(poll_interval=0.05)
    fired = threading.Event()
    sched.add("ping", fired.set, "in 0 seconds")
    sched.start()
    assert fired.wait(timeout=2.0)
    time.sleep(0.1)
    assert sched.list_jobs() == []  # one-shot job removed after firing
    sched.stop()


def test_scheduler_repeats():
    sched = TaskScheduler(poll_interval=0.05)
    counter = {"n": 0}
    sched.add("tick", lambda: counter.__setitem__("n", counter["n"] + 1),
              "every 0 seconds")
    sched.start()
    time.sleep(0.4)
    sched.stop()
    assert counter["n"] >= 2  # fired multiple times
    assert len(sched.list_jobs()) == 1  # repeating job stays registered
