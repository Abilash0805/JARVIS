"""A tiny local web dashboard to drive and watch JARVIS — stdlib only.

Run with ``python -m jarvis.dashboard`` (or ``python -m jarvis --dashboard``).
It serves a single page that submits prompts and shows a live feed of the
agent's tool calls and results. No external web framework, no paid services.

The agent is not safe to run concurrently, so the dashboard runs one request at
a time (returns HTTP 409 if you submit while busy).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from jarvis.app import JarvisRuntime, build_runtime
from jarvis.core.agent import AgentEvent
from jarvis.utils.logging import get_logger

logger = get_logger("jarvis.dashboard")


class _EventBuffer:
    """Thread-safe append-only event log with index-based polling."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._lock = threading.Lock()

    def append(self, event: dict) -> None:
        with self._lock:
            self._events.append(event)

    def since(self, index: int) -> tuple[list[dict], int]:
        with self._lock:
            return self._events[index:], len(self._events)


class DashboardState:
    def __init__(self, runtime: JarvisRuntime) -> None:
        self.runtime = runtime
        self.buffer = _EventBuffer()
        self.busy = False
        self._lock = threading.Lock()

    def try_run(self, prompt: str) -> bool:
        """Start a run in the background. Returns False if already busy."""
        with self._lock:
            if self.busy:
                return False
            self.busy = True
        self.buffer.append({"kind": "user", "text": prompt})

        def worker() -> None:
            try:
                answer = self.runtime.agent.run(
                    prompt, on_event=lambda e: self.buffer.append(_event_dict(e))
                )
                self.buffer.append({"kind": "answer", "text": answer})
            except Exception as exc:  # noqa: BLE001
                self.buffer.append({"kind": "error", "text": str(exc)})
            finally:
                with self._lock:
                    self.busy = False

        threading.Thread(target=worker, daemon=True).start()
        return True


def _event_dict(e: AgentEvent) -> dict:
    return {"kind": e.kind, "text": e.text, "tool": e.tool_name, "detail": e.detail}


def _make_handler(state: DashboardState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence default logging
            pass

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = _PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/state":
                rt = state.runtime
                self._json(200, {
                    "busy": state.busy,
                    "brain": rt.brain_name,
                    "models": list(rt.api_providers),
                    "web": list(rt.web_backends),
                    "tools": len(rt.agent.toolset),
                    "vision": rt.vision_enabled,
                })
            elif parsed.path == "/api/events":
                since = int((parse_qs(parsed.query).get("since", ["0"]))[0])
                events, nxt = state.buffer.since(since)
                self._json(200, {"events": events, "next": nxt, "busy": state.busy})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/run":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            prompt = (data.get("prompt") or "").strip()
            if not prompt:
                self._json(400, {"error": "empty prompt"})
                return
            if not state.try_run(prompt):
                self._json(409, {"error": "busy"})
                return
            self._json(202, {"status": "started"})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765, enable_web: bool = False) -> None:
    runtime = build_runtime(enable_web=enable_web)
    if runtime.scheduler:
        runtime.scheduler.start()
    state = DashboardState(runtime)
    server = ThreadingHTTPServer((host, port), _make_handler(state))
    print(f"JARVIS dashboard on http://{host}:{port}  (brain: {runtime.brain_name})")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down.")
        server.shutdown()


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: ui-monospace, Menlo, Consolas, monospace; margin: 0;
         background: #0b0f17; color: #d7e0ee; }
  header { padding: 14px 18px; background: #111826; border-bottom: 1px solid #1e293b;
           display: flex; gap: 16px; align-items: baseline; }
  h1 { font-size: 18px; margin: 0; color: #5eead4; letter-spacing: 2px; }
  #meta { font-size: 12px; color: #7c8aa5; }
  #feed { padding: 16px 18px; height: calc(100vh - 150px); overflow-y: auto; }
  .row { margin: 6px 0; padding: 6px 10px; border-radius: 6px; white-space: pre-wrap;
         word-break: break-word; font-size: 13px; }
  .user { background: #1d283a; color: #cbd5e1; }
  .tool_call { color: #38bdf8; } .tool_result { color: #4ade80; }
  .thinking { color: #94a3b8; font-style: italic; }
  .answer { background: #14532d33; color: #bbf7d0; border: 1px solid #16653433; }
  .error { color: #f87171; }
  .tag { color: #64748b; }
  form { display: flex; gap: 8px; padding: 14px 18px; border-top: 1px solid #1e293b;
         background: #111826; }
  input { flex: 1; padding: 10px 12px; border-radius: 6px; border: 1px solid #334155;
          background: #0b0f17; color: #e2e8f0; font-size: 14px; }
  button { padding: 10px 18px; border: 0; border-radius: 6px; background: #14b8a6;
           color: #04211c; font-weight: 700; cursor: pointer; }
  button:disabled { opacity: .5; cursor: not-allowed; }
</style></head><body>
<header><h1>J.A.R.V.I.S</h1><span id="meta">connecting…</span></header>
<div id="feed"></div>
<form id="f"><input id="p" placeholder="Tell JARVIS what to do…" autocomplete="off">
<button id="b" type="submit">Send</button></form>
<script>
let since = 0;
const feed = document.getElementById('feed');
const meta = document.getElementById('meta');
function add(e){
  const d = document.createElement('div');
  d.className = 'row ' + e.kind;
  let body = e.text || '';
  if (e.kind === 'tool_call') body = '→ ' + e.tool + '  ' + (e.detail||'');
  else if (e.kind === 'tool_result') body = '✓ ' + e.tool + '  ' + (e.detail||'').slice(0,400);
  else if (e.kind === 'user') body = 'you: ' + body;
  else if (e.kind === 'answer') body = 'JARVIS: ' + body;
  d.textContent = body;
  feed.appendChild(d); feed.scrollTop = feed.scrollHeight;
}
async function poll(){
  try {
    const r = await fetch('/api/events?since=' + since);
    const j = await r.json();
    j.events.forEach(add); since = j.next;
    document.getElementById('b').disabled = j.busy;
  } catch(_) {}
  setTimeout(poll, 600);
}
async function state(){
  try { const j = await (await fetch('/api/state')).json();
    meta.textContent = 'brain: ' + j.brain + ' · ' + j.tools + ' tools · vision: ' + j.vision
      + (j.web.length ? ' · web: ' + j.web.join(',') : ''); } catch(_) {}
}
document.getElementById('f').addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const p = document.getElementById('p'); const text = p.value.trim();
  if (!text) return; p.value = '';
  const r = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({prompt: text})});
  if (r.status === 409) add({kind:'error', text:'busy — wait for the current task'});
});
state(); poll();
</script></body></html>"""


if __name__ == "__main__":
    serve()
