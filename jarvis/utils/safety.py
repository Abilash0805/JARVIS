"""Action gate for tool execution.

By default JARVIS runs **autonomously**: it does not ask the user to confirm
each action, so it can build whole websites, decks, PDFs and study packs end to
end without interruption. The only thing that still stops an action is a small
``hard_blocklist`` of catastrophic, machine-destroying commands — this is an
accident guard against a model hallucinating something like ``rm -rf /``, not a
permission prompt. It can be turned off entirely (see ``from_env``).

Modes (controlled by env):
- ``JARVIS_REQUIRE_CONFIRMATION=true``  -> ask before each dangerous action.
- ``JARVIS_REQUIRE_CONFIRMATION=false`` (default) -> run without prompting.
- ``JARVIS_DISABLE_BLOCKLIST=true``     -> remove even the catastrophic guard.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Optional


class SafetyGate:
    """Decide whether an action may proceed.

    Parameters
    ----------
    require_confirmation:
        When True, ask before each dangerous action. When False (default),
        allow actions to run without prompting.
    prompt:
        Callable that asks the user and returns True to allow. Defaults to a
        terminal y/N prompt. Only used when ``require_confirmation`` is True.
    allow_when_noninteractive:
        What to do for a dangerous action when there is no TTY to prompt and
        confirmation is required. Defaults to True so headless/scheduled runs
        keep working.
    enforce_blocklist:
        When True (default), refuse the handful of catastrophic commands in
        ``hard_blocklist`` regardless of mode. Set False to remove every guard.
    """

    def __init__(
        self,
        require_confirmation: bool = False,
        prompt: Optional[Callable[[str], bool]] = None,
        allow_when_noninteractive: bool = True,
        enforce_blocklist: bool = True,
    ) -> None:
        self.require_confirmation = require_confirmation
        self._prompt = prompt or self._default_prompt
        self.allow_when_noninteractive = allow_when_noninteractive
        self.enforce_blocklist = enforce_blocklist
        # Catastrophic, irreversible whole-system commands. This is an accident
        # guard (a model can hallucinate these), not a permission prompt.
        self.hard_blocklist: list[str] = [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            ":(){ :|:& };:",  # fork bomb
            "mkfs",
            "dd if=/dev/zero of=/dev/",
            "dd if=/dev/random of=/dev/",
            "> /dev/sda",
            "format c:",
        ]

    @classmethod
    def from_env(cls) -> "SafetyGate":
        # Autonomous by default: only prompt if explicitly asked to.
        require = os.getenv("JARVIS_REQUIRE_CONFIRMATION", "false").lower() == "true"
        enforce = os.getenv("JARVIS_DISABLE_BLOCKLIST", "false").lower() != "true"
        return cls(require_confirmation=require, enforce_blocklist=enforce)

    def is_hard_blocked(self, action: str) -> bool:
        if not self.enforce_blocklist:
            return False
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
