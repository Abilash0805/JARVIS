"""Desktop-app integrations: Claude desktop and Cursor.

Desktop apps have no clean text-in/text-out API, so these helpers drive them
through window focus + keyboard automation. They are best-effort and intended
to run on the user's machine with a desktop session.
"""

from jarvis.integrations.desktop.desktop_app import (
    ClaudeDesktop,
    CursorDesktop,
    DesktopApp,
)

__all__ = ["ClaudeDesktop", "CursorDesktop", "DesktopApp"]
