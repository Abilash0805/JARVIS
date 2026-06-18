"""Confirmation gate for potentially destructive actions.

The gate sits between the agent and any tool marked ``dangerous`` (shell
commands, PC control, file writes/deletes). In interactive mode it prompts the
user; in non-interactive mode it follows a configured default.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Optional


class SafetyGate:
    """Decide whether a dangerous action may proceed.

    Parameters
    ----------
    require_confirmation:
        When True, ask before each dangerous action. When False, allow
        everything (use only when you trust the task fully).
    prompt:
        Callable that asks the user and returns True to allow. Defaults to a
        terminal y/N prompt. In non-interactive sessions (no TTY) the gate
        falls back to ``allow_when_noninteractive``.
    allow_when_noninteractive:
        What to do for a dangerous action when there is no TTY to prompt.
    """

    def __init__(
        self,
        require_confirmation: bool = True,
        prompt: Optional[Callable[[str], bool]] = None,
        allow_when_noninteractive: bool = False,
    ) -> None:
        self.require_confirmation = require_confirmation
        self._prompt = prompt or self._default_prompt
        self.allow_when_noninteractive = allow_when_noninteractive
        # Commands that are never allowed, confirmation or not.
        self.hard_blocklist: list[str] = [
            "rm -rf /",
            "rm -rf /*",
            ":(){ :|:& };:",  # fork bomb
            "mkfs",
            "dd if=/dev/zero of=/dev/",
            "format c:",
        ]

    @classmethod
    def from_env(cls) -> "SafetyGate":
        require = os.getenv("JARVIS_REQUIRE_CONFIRMATION", "true").lower() != "false"
        return cls(require_confirmation=require)

    def is_hard_blocked(self, action: str) -> bool:
        lowered = action.lower()
        return any(pattern in lowered for pattern in self.hard_blocklist)

    def confirm(self, description: str) -> bool:
        """Return True if the action may proceed."""
        if self.is_hard_blocked(description):
            return False
        if not self.require_confirmation:
            return True
        if not sys.stdin.isatty():
            return self.allow_when_noninteractive
        return self._prompt(description)

    @staticmethod
    def _default_prompt(description: str) -> bool:
        try:
            answer = input(f"\n[JARVIS] Allow this action?\n  {description}\n  [y/N] ")
        except (EOFError, KeyboardInterrupt):
            return False
        return answer.strip().lower() in {"y", "yes"}
