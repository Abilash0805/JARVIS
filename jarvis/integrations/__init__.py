"""External app integrations: browser-based AIs and desktop apps.

These are optional and require a real desktop session. Builders return ``None``
when their dependency (playwright / pygetwindow) is unavailable, so the rest of
JARVIS keeps working.
"""

from jarvis.integrations.factory import build_web_backends

__all__ = ["build_web_backends"]
