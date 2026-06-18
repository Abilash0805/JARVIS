"""Tools JARVIS can call to act on the world.

Each tool is a :class:`Tool` with a JSON-schema parameter spec, exposed to the
model via OpenAI function-calling. :func:`default_toolset` returns the standard
set wired with a :class:`~jarvis.utils.safety.SafetyGate`.
"""

from jarvis.tools.base import Tool, ToolError, Toolset
from jarvis.tools.registry import default_toolset

__all__ = ["Tool", "ToolError", "Toolset", "default_toolset"]
