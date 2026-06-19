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

        def emit(e) -> None:
            self.buffer.append(_event_dict(e))

        def worker() -> None:
            # Route nested specialist progress to the same feed.
            if self.runtime.sink:
                self.runtime.sink.callback = emit
            try:
                answer = self.runtime.agent.run(prompt, on_event=emit)
                self.buffer.append({"kind": "answer", "text": answer})
            except Exception as exc:  # noqa: BLE001
                self.buffer.append({"kind": "error", "text": str(exc)})
            finally:
                if self.runtime.sink:
                    self.runtime.sink.callback = None
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
                    "team": list(rt.team),
                    "tools": len(rt.agent.toolset),
                    "vision": rt.vision_enabled,
                    "autonomous": not rt.config.require_confirmation,
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
<title>J.A.R.V.I.S</title>
<style>
  :root{
    color-scheme: dark;
    --bg:#05070d; --panel:rgba(13,20,33,.72); --line:rgba(56,189,248,.16);
    --cyan:#38e8ff; --teal:#5eead4; --ice:#bce7ff; --txt:#d7e6f7;
    --muted:#6f86a8; --gold:#ffd166; --green:#4ade80; --red:#ff6b81;
    --glow:0 0 22px rgba(56,232,255,.45);
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; color:var(--txt); background:var(--bg);
    font-family:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif;
    overflow:hidden;
  }
  /* animated grid + aurora backdrop */
  .bg{position:fixed; inset:0; z-index:-2; overflow:hidden; background:
      radial-gradient(1200px 700px at 78% -10%, rgba(56,232,255,.10), transparent 60%),
      radial-gradient(900px 600px at -5% 110%, rgba(94,234,212,.08), transparent 55%),
      var(--bg);}
  .bg::before{content:""; position:absolute; inset:-2px; z-index:-1;
    background-image:linear-gradient(rgba(56,189,248,.06) 1px,transparent 1px),
      linear-gradient(90deg,rgba(56,189,248,.06) 1px,transparent 1px);
    background-size:44px 44px; mask-image:radial-gradient(circle at 50% 40%,#000 30%,transparent 85%);
    animation:drift 24s linear infinite;}
  @keyframes drift{from{background-position:0 0,0 0}to{background-position:44px 88px,88px 44px}}
  .scan{position:fixed; left:0; right:0; height:140px; z-index:-1; pointer-events:none;
    background:linear-gradient(180deg,transparent,rgba(56,232,255,.05),transparent);
    animation:scan 7s ease-in-out infinite;}
  @keyframes scan{0%{top:-140px}100%{top:100%}}

  .app{display:flex; flex-direction:column; height:100vh; max-width:1180px; margin:0 auto;
    padding:0 18px;}

  /* header */
  header{display:flex; align-items:center; gap:18px; padding:18px 6px 14px;}
  .reactor{width:46px; height:46px; border-radius:50%; position:relative; flex:0 0 auto;
    background:radial-gradient(circle,#bff7ff 0%,#38e8ff 38%,#0b3a4a 70%,#06121b 100%);
    box-shadow:var(--glow),inset 0 0 10px rgba(0,0,0,.6); animation:pulse 2.6s ease-in-out infinite;}
  .reactor::after{content:""; position:absolute; inset:-6px; border-radius:50%;
    border:1px solid rgba(56,232,255,.5); border-top-color:transparent; border-left-color:transparent;
    animation:spin 4.5s linear infinite;}
  .reactor.busy{animation:pulse 1s ease-in-out infinite}
  @keyframes pulse{0%,100%{box-shadow:0 0 14px rgba(56,232,255,.35),inset 0 0 10px rgba(0,0,0,.6)}
    50%{box-shadow:0 0 30px rgba(56,232,255,.75),inset 0 0 10px rgba(0,0,0,.6)}}
  @keyframes spin{to{transform:rotate(360deg)}}
  .title{display:flex; flex-direction:column; gap:3px}
  h1{margin:0; font-size:22px; font-weight:800; letter-spacing:7px; color:#eaf9ff;
    text-shadow:0 0 18px rgba(56,232,255,.5);}
  h1 b{color:var(--cyan)}
  .sub{font-size:11px; letter-spacing:3px; text-transform:uppercase; color:var(--muted)}
  .spacer{flex:1}
  .status{display:flex; align-items:center; gap:8px; font-size:12px; color:var(--teal);
    letter-spacing:1px; text-transform:uppercase}
  .dot{width:9px; height:9px; border-radius:50%; background:var(--green);
    box-shadow:0 0 10px var(--green); animation:blink 2s infinite}
  .dot.busy{background:var(--gold); box-shadow:0 0 10px var(--gold)}
  @keyframes blink{50%{opacity:.4}}

  /* chips */
  .chips{display:flex; flex-wrap:wrap; gap:8px; padding:0 6px 12px}
  .chip{font-size:11px; letter-spacing:.5px; padding:5px 11px; border-radius:999px;
    background:rgba(56,189,248,.07); border:1px solid var(--line); color:var(--ice);
    display:flex; gap:6px; align-items:center; backdrop-filter:blur(6px)}
  .chip span{color:var(--muted)}
  .chip b{color:var(--cyan); font-weight:700}

  /* feed */
  #feed{flex:1; overflow-y:auto; padding:8px 4px 18px; display:flex; flex-direction:column; gap:10px}
  #feed::-webkit-scrollbar{width:8px}
  #feed::-webkit-scrollbar-thumb{background:rgba(56,189,248,.25); border-radius:8px}
  .row{position:relative; padding:11px 14px 11px 16px; border-radius:12px; font-size:13.5px;
    line-height:1.5; white-space:pre-wrap; word-break:break-word; max-width:88%;
    border:1px solid var(--line); background:var(--panel); backdrop-filter:blur(8px);
    animation:rise .28s ease both; box-shadow:0 6px 18px rgba(0,0,0,.25)}
  @keyframes rise{from{opacity:0; transform:translateY(8px)}to{opacity:1; transform:none}}
  .row .lbl{display:block; font-size:10px; letter-spacing:1.5px; text-transform:uppercase;
    margin-bottom:4px; color:var(--muted)}
  .row::before{content:""; position:absolute; left:0; top:8px; bottom:8px; width:3px;
    border-radius:3px; background:var(--cyan)}
  .user{align-self:flex-end; background:linear-gradient(135deg,rgba(56,189,248,.16),rgba(94,234,212,.10));
    border-color:rgba(94,234,212,.3)}
  .user::before{background:var(--teal)}
  .user .lbl{color:var(--teal)}
  .answer{align-self:flex-start; background:linear-gradient(135deg,rgba(20,83,45,.32),rgba(13,20,33,.7));
    border-color:rgba(74,222,128,.28); font-size:14px}
  .answer::before{background:var(--green)}
  .answer .lbl{color:var(--green)}
  .thinking{color:#9fb3cf; font-style:italic; background:transparent; border-style:dashed; box-shadow:none}
  .thinking::before{background:#5b7290}
  .tool_call{font-family:ui-monospace,Consolas,monospace; color:var(--cyan)}
  .tool_call::before{background:var(--cyan)}
  .tool_result{font-family:ui-monospace,Consolas,monospace; color:#b8f5d6}
  .tool_result::before{background:var(--green)}
  .error{color:#ffd0d8; background:rgba(255,107,129,.10); border-color:rgba(255,107,129,.35)}
  .error::before{background:var(--red)}
  .tname{color:var(--ice); font-weight:700}

  /* working indicator */
  #work{display:none; align-self:flex-start; align-items:center; gap:10px; padding:8px 14px;
    color:var(--cyan); font-size:12px; letter-spacing:2px; text-transform:uppercase}
  #work.on{display:flex}
  #work i{width:7px; height:7px; border-radius:50%; background:var(--cyan); box-shadow:0 0 8px var(--cyan);
    animation:bounce 1.2s infinite}
  #work i:nth-child(2){animation-delay:.18s} #work i:nth-child(3){animation-delay:.36s}
  @keyframes bounce{0%,80%,100%{transform:scale(.5); opacity:.4}40%{transform:scale(1); opacity:1}}

  /* composer */
  form{display:flex; gap:10px; padding:14px 4px 20px}
  .field{flex:1; position:relative}
  input{width:100%; padding:15px 16px; border-radius:14px; font-size:14.5px; color:#eaf6ff;
    background:rgba(8,14,24,.85); border:1px solid var(--line); outline:none;
    transition:border-color .2s, box-shadow .2s; backdrop-filter:blur(8px)}
  input::placeholder{color:#56708f}
  input:focus{border-color:rgba(56,232,255,.6); box-shadow:0 0 0 3px rgba(56,232,255,.12),var(--glow)}
  button{padding:0 26px; border:0; border-radius:14px; cursor:pointer; font-weight:800;
    letter-spacing:2px; font-size:13px; text-transform:uppercase; color:#021018;
    background:linear-gradient(135deg,#7ef0ff,#38e8ff 45%,#22b8d6); box-shadow:var(--glow);
    transition:transform .12s, filter .2s}
  button:hover:not(:disabled){transform:translateY(-1px); filter:brightness(1.1)}
  button:active:not(:disabled){transform:translateY(0)}
  button:disabled{opacity:.45; cursor:not-allowed; box-shadow:none}
  @media(max-width:620px){h1{font-size:18px; letter-spacing:4px} .row{max-width:96%}}
</style></head><body>
<div class="bg"></div><div class="scan"></div>
<div class="app">
  <header>
    <div class="reactor" id="reactor"></div>
    <div class="title"><h1>J<b>.</b>A<b>.</b>R<b>.</b>V<b>.</b>I<b>.</b>S</h1>
      <div class="sub">Just A Rather Very Intelligent System</div></div>
    <div class="spacer"></div>
    <div class="status"><span class="dot" id="dot"></span><span id="stat">online</span></div>
  </header>
  <div class="chips" id="chips"></div>
  <div id="feed"></div>
  <div id="work"><span>processing</span><i></i><i></i><i></i></div>
  <form id="f">
    <div class="field"><input id="p" placeholder="Tell JARVIS what to build — a deck, a PDF, a website…" autocomplete="off"></div>
    <button id="b" type="submit">Send</button>
  </form>
</div>
<script>
let since=0, busy=false;
const feed=document.getElementById('feed'), work=document.getElementById('work');
const reactor=document.getElementById('reactor'), dot=document.getElementById('dot'), stat=document.getElementById('stat');
const LABELS={user:'You',answer:'JARVIS',thinking:'Reasoning',tool_call:'Action',tool_result:'Result',error:'Alert'};
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function add(e){
  const d=document.createElement('div'); d.className='row '+e.kind;
  let inner='';
  if(e.kind==='tool_call') inner='→ <span class="tname">'+esc(e.tool)+'</span>  '+esc(e.detail||'');
  else if(e.kind==='tool_result') inner='✓ <span class="tname">'+esc(e.tool)+'</span>  '+esc((e.detail||'').slice(0,500));
  else inner=esc(e.text||'');
  d.innerHTML='<span class="lbl">'+(LABELS[e.kind]||e.kind)+'</span>'+inner;
  feed.appendChild(d); feed.scrollTop=feed.scrollHeight;
}
function setBusy(b){
  busy=b; document.getElementById('b').disabled=b;
  work.classList.toggle('on',b); reactor.classList.toggle('busy',b);
  dot.classList.toggle('busy',b); stat.textContent=b?'working':'online';
  if(b) feed.scrollTop=feed.scrollHeight;
}
async function poll(){
  try{
    const j=await (await fetch('/api/events?since='+since)).json();
    j.events.forEach(add); since=j.next; setBusy(j.busy);
  }catch(_){}
  setTimeout(poll,500);
}
function chip(label,val){return '<div class="chip"><span>'+label+'</span><b>'+val+'</b></div>';}
async function state(){
  try{
    const j=await (await fetch('/api/state')).json();
    let h=chip('brain',j.brain)+chip('tools',j.tools)+chip('mode',j.autonomous?'autonomous':'ask-first');
    h+=chip('vision',j.vision?'on':'off');
    if(j.models.length) h+=chip('models',j.models.join(' · '));
    if(j.team&&j.team.length) h+=chip('team',j.team.join(' · '));
    if(j.web&&j.web.length) h+=chip('web',j.web.join(' · '));
    document.getElementById('chips').innerHTML=h;
  }catch(_){}
}
document.getElementById('f').addEventListener('submit',async ev=>{
  ev.preventDefault();
  const p=document.getElementById('p'), text=p.value.trim();
  if(!text||busy) return; p.value='';
  const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:text})});
  if(r.status===409) add({kind:'error',text:'Busy — wait for the current task to finish.'});
});
state(); setInterval(state,5000); poll();
</script></body></html>"""


if __name__ == "__main__":
    serve()
