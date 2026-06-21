"""Tests for the hardened safety gate and filesystem confinement — areas
that had zero coverage before."""

from __future__ import annotations

import pytest

from jarvis.tools.base import ToolError
from jarvis.utils.safety import SafetyGate


# --------------------------------------------------------------------------
# SafetyGate: obfuscation resistance
# --------------------------------------------------------------------------

class TestSafetyGateBlocklist:
    def setup_method(self):
        self.gate = SafetyGate(require_confirmation=False)

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "rm  -rf   /",  # extra whitespace
            "RM -RF /",  # case
            "rm -rf --no-preserve-root /",
            ":(){ :|:& };:",  # fork bomb
            ":(){:|:&};:",  # fork bomb, no spaces
            ": () { : | : & } ; :",  # fork bomb, loose spacing (regex catches)
            "mkfs.ext4 /dev/sda1",
            "dd if=/dev/zero of=/dev/sda",
            "dd if=/dev/zero of=/dev/nvme0n1",
            "> /dev/sda",
            ">/dev/sda",
            "format c:",
            "FORMAT D:",
            "del /s /q c:\\",
            "rd /s /q c:\\",
        ],
    )
    def test_catastrophic_commands_blocked(self, command):
        assert self.gate.is_hard_blocked(command) is True
        assert self.gate.confirm(f"RUN shell command:\n    {command}") is False

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf ./build",
            "rm -rf /tmp/scratch",
            "rm -rf node_modules",
            "ls -la /",
            "dd if=/dev/zero of=output.img bs=1M count=10",
            "mkdir formatted_output",
        ],
    )
    def test_safe_lookalikes_not_blocked(self, command):
        # These resemble dangerous patterns but operate on safe, scoped
        # targets and should NOT be caught by the accident guard.
        assert self.gate.is_hard_blocked(command) is False

    def test_known_limitation_text_mentioning_a_pattern_is_also_blocked(self):
        # Substring/regex matching can't distinguish "running a command" from
        # "talking about a command" — text that merely *mentions* a blocked
        # phrase is also flagged. This is a documented tradeoff: a false
        # positive just means rephrasing, while a false negative could be
        # destructive, so the gate errs toward blocking.
        assert self.gate.is_hard_blocked("echo 'format c: is dangerous'") is True

    def test_blocklist_can_be_disabled(self):
        open_gate = SafetyGate(enforce_blocklist=False)
        assert open_gate.is_hard_blocked("rm -rf /") is False
        assert open_gate.confirm("rm -rf /") is True

    def test_require_confirmation_mode_blocks_even_with_approval(self):
        # Even if the (stubbed) prompt would say yes, hard-blocked actions
        # never reach the prompt.
        gate = SafetyGate(require_confirmation=True, prompt=lambda _d: True)
        assert gate.confirm("rm -rf /") is False

    def test_noninteractive_default_allows_when_confirmation_required(self):
        gate = SafetyGate(require_confirmation=True, allow_when_noninteractive=True)
        # No TTY in the test runner, so this should fall through to "allow".
        assert gate.confirm("WRITE file /tmp/x") is True


# --------------------------------------------------------------------------
# Filesystem confinement (JARVIS_FS_ROOT)
# --------------------------------------------------------------------------

class TestFilesystemConfinement:
    def test_unconfined_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JARVIS_FS_ROOT", raising=False)
        from jarvis.tools.filesystem import make_filesystem_tools

        gate = SafetyGate(require_confirmation=False)
        tools = {t.name: t for t in make_filesystem_tools(gate)}
        outside = tmp_path / "outside.txt"
        result = tools["write_file"].func(path=str(outside), content="hi")
        assert "wrote" in result
        assert outside.read_text() == "hi"

    def test_confined_write_inside_root_succeeds(self, tmp_path, monkeypatch):
        root = tmp_path / "workspace"
        root.mkdir()
        monkeypatch.setenv("JARVIS_FS_ROOT", str(root))
        from jarvis.tools.filesystem import make_filesystem_tools

        gate = SafetyGate(require_confirmation=False)
        tools = {t.name: t for t in make_filesystem_tools(gate)}
        inside = root / "notes.txt"
        result = tools["write_file"].func(path=str(inside), content="hi")
        assert "wrote" in result

    def test_confined_write_outside_root_blocked(self, tmp_path, monkeypatch):
        root = tmp_path / "workspace"
        root.mkdir()
        monkeypatch.setenv("JARVIS_FS_ROOT", str(root))
        from jarvis.tools.filesystem import make_filesystem_tools

        gate = SafetyGate(require_confirmation=False)
        tools = {t.name: t for t in make_filesystem_tools(gate)}
        outside = tmp_path / "elsewhere.txt"
        with pytest.raises(ToolError, match="outside the confined workspace"):
            tools["write_file"].func(path=str(outside), content="hi")

    def test_confined_read_outside_root_blocked(self, tmp_path, monkeypatch):
        root = tmp_path / "workspace"
        root.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret")
        monkeypatch.setenv("JARVIS_FS_ROOT", str(root))
        from jarvis.tools.filesystem import make_filesystem_tools

        gate = SafetyGate(require_confirmation=False)
        tools = {t.name: t for t in make_filesystem_tools(gate)}
        with pytest.raises(ToolError, match="outside the confined workspace"):
            tools["read_file"].func(path=str(secret))

    def test_confined_delete_outside_root_blocked(self, tmp_path, monkeypatch):
        root = tmp_path / "workspace"
        root.mkdir()
        victim = tmp_path / "victim.txt"
        victim.write_text("don't delete me")
        monkeypatch.setenv("JARVIS_FS_ROOT", str(root))
        from jarvis.tools.filesystem import make_filesystem_tools

        gate = SafetyGate(require_confirmation=False)
        tools = {t.name: t for t in make_filesystem_tools(gate)}
        with pytest.raises(ToolError, match="outside the confined workspace"):
            tools["delete_file"].func(path=str(victim))
        assert victim.exists()  # still there
