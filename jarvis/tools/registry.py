"""Assemble the default toolset."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from jarvis.tools.apps import make_app_tools
from jarvis.tools.base import Toolset
from jarvis.tools.filesystem import make_filesystem_tools
from jarvis.tools.pc_control import make_pc_control_tools
from jarvis.tools.shell import make_shell_tools
from jarvis.tools.system_info import make_system_info_tools
from jarvis.utils.safety import SafetyGate

if TYPE_CHECKING:
    from jarvis.core.longterm import LongTermMemory
    from jarvis.providers.base import LLMProvider
    from jarvis.providers.openai_compatible import OpenAICompatibleProvider


def default_toolset(
    gate: Optional[SafetyGate] = None,
    *,
    api_providers: Optional[dict[str, "LLMProvider"]] = None,
    web_backends: Optional[dict[str, object]] = None,
    vision_provider: Optional["OpenAICompatibleProvider"] = None,
    longterm: Optional["LongTermMemory"] = None,
    include_pc_control: bool = True,
) -> Toolset:
    """Build the standard toolset.

    Parameters
    ----------
    gate:
        Safety gate for dangerous actions; one is created from env if omitted.
    api_providers / web_backends:
        When given, an ``ask_model`` delegation tool is added so JARVIS can
        route subtasks to other models.
    include_pc_control:
        Set False on headless servers to omit keyboard/mouse/app tools.
    """
    gate = gate or SafetyGate.from_env()
    ts = Toolset()
    ts.extend(make_filesystem_tools(gate))
    ts.extend(make_shell_tools(gate))
    ts.extend(make_system_info_tools())
    if include_pc_control:
        ts.extend(make_pc_control_tools(gate))
        ts.extend(make_app_tools(gate))
    if api_providers or web_backends:
        from jarvis.tools.ai_delegate import make_ai_delegate_tools

        ts.extend(make_ai_delegate_tools(api_providers or {}, web_backends or {}))
    if vision_provider is not None:
        from jarvis.tools.vision import make_vision_tools

        ts.extend(make_vision_tools(vision_provider))
    if longterm is not None:
        from jarvis.tools.memory_tools import make_memory_tools

        ts.extend(make_memory_tools(longterm))
    return ts
