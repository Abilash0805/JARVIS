"""Interactive JARVIS command line."""

from __future__ import annotations

import sys

from jarvis.app import build_runtime
from jarvis.core.agent import AgentEvent
from jarvis.providers.base import ProviderError

_BANNER = r"""
       _  ____     ____     _    _ ___ ____
      | |/ \  \   / /  \   | |  | |_ _/ ___|
   _  | / _ \ \ / / /\ \  | |  | || |\___ \
  | |_| / ___ \ V / ____ \ | |__| || | ___) |
   \___/_/   \_\_/_/    \_\ \____/|___|____/
"""


def _make_printer():
    try:
        from rich.console import Console

        console = Console()

        def emit(event: AgentEvent) -> None:
            if event.kind == "thinking":
                console.print(f"[dim]…{event.text}[/dim]")
            elif event.kind == "tool_call":
                console.print(f"[cyan]→ {event.tool_name}[/cyan] [dim]{event.detail}[/dim]")
            elif event.kind == "tool_result":
                snippet = event.detail[:300]
                console.print(f"[green]✓ {event.tool_name}[/green] [dim]{snippet}[/dim]")
            elif event.kind == "error":
                console.print(f"[red]{event.text}[/red]")

        return console, emit
    except ImportError:
        def emit(event: AgentEvent) -> None:
            if event.kind in {"tool_call", "tool_result", "error"}:
                print(f"[{event.kind}] {event.tool_name} {event.detail or event.text}")

        return None, emit


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    console, emit = _make_printer()

    def say(msg: str) -> None:
        console.print(msg) if console else print(msg)

    try:
        runtime = build_runtime(enable_web="--no-web" not in argv)
    except ProviderError as exc:
        say(f"[startup error] {exc}")
        return 1

    # Optional voice mode (offline / free).
    voice = None
    if "--voice" in argv:
        from jarvis.voice import Voice

        voice = Voice()
        say(f"voice: tts={voice.tts_available} stt={voice.stt_available}")

    say(_BANNER)
    say(f"brain: {runtime.brain_name} (+fallback)  |  api models: {', '.join(runtime.api_providers)}")
    if runtime.web_backends:
        say(f"web backends: {', '.join(runtime.web_backends)}")
    say("tools: %d  |  vision: %s  |  confirmation: %s" % (
        len(runtime.agent.toolset), runtime.vision_enabled,
        runtime.config.require_confirmation))
    say("Type your request, or 'exit' to quit.\n")

    # One-shot mode: `python -m jarvis "do something"`
    oneshot = [a for a in argv if not a.startswith("-")]
    if oneshot:
        answer = runtime.agent.run(" ".join(oneshot), on_event=emit)
        say(f"\nJARVIS: {answer}")
        return 0

    while True:
        try:
            if voice and voice.stt_available:
                say("[listening — speak now]")
                user = voice.listen().strip()
                say(f"you> {user}")
            else:
                user = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            say("\nbye.")
            return 0
        except RuntimeError as exc:
            say(f"[voice error] {exc}")
            continue
        if not user:
            continue
        if user.lower() in {"exit", "quit", ":q"}:
            say("bye.")
            return 0
        answer = runtime.agent.run(user, on_event=emit)
        say(f"\nJARVIS: {answer}\n")
        if voice and voice.tts_available:
            voice.speak(answer)


if __name__ == "__main__":
    raise SystemExit(main())
