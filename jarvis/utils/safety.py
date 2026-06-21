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

Honest limitation: ``hard_blocklist`` matches normalized text against known
catastrophic patterns. It catches the obvious cases (including common
whitespace/quoting tricks) but is **not** a sandbox and cannot catch every
possible obfuscation (e.g. a base64-encoded command piped to a shell, or a
multi-step sequence that's only destructive in combination). Treat it as a
seatbelt for accidental model mistakes, not a security boundary against a
genuinely adversarial actor. For real isolation, run JARVIS in a container or
VM, and/or set ``JARVIS_FS_ROOT`` to confine filesystem tools.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable, Optional


def _normalize(text: str) -> str:
    """Collapse whitespace and lowercase so trivial spacing/case tricks
    (``rm  -rf   /``, ``RM -RF /``) don't slip past substring matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


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
        ``hard_blocklist``/``hard_blocklist_patterns`` regardless of mode.
        Set False to remove every guard.
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

        # Catastrophic, irreversible whole-system commands/literals. This is
        # an accident guard (a model can hallucinate these), not a permission
        # prompt. Plain substrings — fast, exact, easy to audit. Note these
        # specifically target root-like paths (trailing space/end-of-string
        # after the path) so `rm -rf /tmp/scratch` is NOT caught here — only
        # the regex patterns below decide root-vs-subdirectory precisely.
        self.hard_blocklist: list[str] = [
            ":(){ :|:& };:",  # fork bomb
            "mkfs",
            "dd if=/dev/zero of=/dev/",
            "dd if=/dev/random of=/dev/",
            "dd if=/dev/urandom of=/dev/",
            "> /dev/sda",
            ">/dev/sda",
            "del /s /q c:\\",
            "rd /s /q c:\\",
            "rmdir /s /q c:\\",
            "shutdown -r -t 0",
            ":(){:|:&};:",  # fork bomb, no spaces
        ]

        # Regex variants, matched against normalized (whitespace-collapsed,
        # lowercased) text. These carry the path-sensitive checks — e.g.
        # `rm -rf /` (root) is blocked but `rm -rf /tmp/scratch` is not,
        # because the path must end right after the slash/tilde to count as
        # "the whole filesystem", not a subdirectory.
        self.hard_blocklist_patterns: list[re.Pattern[str]] = [
            re.compile(r"rm\s+(-\w*\s+)*-[rR]f\S*\s+/(\s|$)"),  # rm -rf / (root only)
            re.compile(r"rm\s+(-\w*\s+)*-[rR]f\S*\s+/\*(\s|$)"),  # rm -rf /*
            re.compile(r"rm\s+(-\w*\s+)*-[rR]f\S*\s+~(\s|$)"),  # rm -rf ~ (home root)
            re.compile(r"rm\s+(-\w*\s+)*-[rR]f\S*\s+--no-preserve-root"),
            re.compile(r":\s*\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb, loose spacing
            re.compile(r"dd\s+.*of=/dev/(sd|nvme|hd)\w*"),  # dd onto a real disk device
            re.compile(r">\s*/dev/(sd|nvme|hd)\w*"),  # redirect onto a real disk device
            re.compile(r"format\s+[a-z]:"),  # format <drive>: (any drive letter)
            re.compile(r"(del|rd|rmdir)\s+/s\s+/q\s+[a-z]:\\\\?\s*$"),  # wipe a whole drive
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
        normalized = _normalize(action)
        if any(pattern in normalized for pattern in self.hard_blocklist):
            return True
        return any(p.search(normalized) for p in self.hard_blocklist_patterns)

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
