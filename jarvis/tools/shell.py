"""Run shell commands. Gated behind confirmation because it is powerful."""

from __future__ import annotations

import platform
import subprocess

from jarvis.tools.base import Tool, ToolError
from jarvis.utils.safety import SafetyGate


def make_shell_tools(gate: SafetyGate) -> list[Tool]:
    is_windows = platform.system() == "Windows"

    def run_command(command: str, timeout: int = 60) -> str:
        if not gate.confirm(f"RUN shell command:\n    {command}"):
            raise ToolError("command denied by safety gate")
        try:
            # On Windows this runs via cmd.exe; elsewhere via the shell.
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"command timed out after {timeout}s")
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        parts = [f"exit_code={result.returncode}"]
        if out:
            parts.append(f"stdout:\n{out[:8000]}")
        if err:
            parts.append(f"stderr:\n{err[:4000]}")
        return "\n".join(parts)

    shell_name = "cmd.exe / PowerShell" if is_windows else "the system shell"
    return [
        Tool(
            "run_command",
            f"Run a command line in {shell_name} and return its output. "
            "Use for launching programs, scripting, and system tasks.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "the command to run"},
                    "timeout": {"type": "integer", "description": "seconds before abort"},
                },
                "required": ["command"],
            },
            run_command,
            dangerous=True,
        )
    ]
