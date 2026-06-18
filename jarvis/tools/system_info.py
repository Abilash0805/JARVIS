"""Read-only system information tools (safe, never gated)."""

from __future__ import annotations

import platform
import shutil
from datetime import datetime

from jarvis.tools.base import Tool


def make_system_info_tools() -> list[Tool]:
    def system_info() -> str:
        lines = [
            f"os: {platform.system()} {platform.release()}",
            f"machine: {platform.machine()}",
            f"python: {platform.python_version()}",
            f"time: {datetime.now().isoformat(timespec='seconds')}",
        ]
        try:
            import psutil

            mem = psutil.virtual_memory()
            lines.append(f"cpu_count: {psutil.cpu_count()}")
            lines.append(f"cpu_percent: {psutil.cpu_percent(interval=0.1)}%")
            lines.append(
                f"memory: {mem.percent}% used "
                f"({mem.used // 2**20} / {mem.total // 2**20} MiB)"
            )
            du = shutil.disk_usage("/")
            lines.append(f"disk_free: {du.free // 2**30} GiB / {du.total // 2**30} GiB")
        except ImportError:
            lines.append("(install psutil for cpu/memory/disk stats)")
        return "\n".join(lines)

    def list_processes(limit: int = 15) -> str:
        try:
            import psutil
        except ImportError:
            return "psutil not installed"
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
            procs.append(p.info)
        procs.sort(key=lambda d: d.get("cpu_percent") or 0, reverse=True)
        head = procs[: max(1, limit)]
        return "\n".join(
            f"{p['pid']:>7}  {p.get('cpu_percent', 0):>5}%  {p['name']}" for p in head
        )

    return [
        Tool(
            "system_info", "Get OS, CPU, memory and disk information for this machine.",
            {"type": "object", "properties": {}},
            system_info,
        ),
        Tool(
            "list_processes", "List the top running processes by CPU usage.",
            {"type": "object", "properties": {"limit": {"type": "integer"}}},
            list_processes,
        ),
    ]
