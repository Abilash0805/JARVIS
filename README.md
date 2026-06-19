# JARVIS

A multi-provider AI assistant that can **control your PC** and **delegate to other
AI models**. JARVIS uses one model as its reasoning "brain", exposes your
computer to it through a safe tool layer (shell, files, keyboard/mouse,
screenshots, app launching), and can route subtasks to other models — including
**Gemini** and **ChatGPT** in a real browser, and the free-tier APIs of **Groq,
Cerebras, Mistral, and NVIDIA Nemotron**.

> **Target OS:** Windows (PC-control layer is Windows-first; shell/file/API
> layers are cross-platform). It runs on macOS/Linux too, minus some Windows
> app shortcuts.

---

> **100% free.** Every backend is a free-tier API or a free/offline local
> library. No paid services are required anywhere.

## What it can do

- **Multi-agent team** — a lead orchestrator asks a **planner** for a
  step-by-step plan, then delegates each step to specialists (**coder**,
  **operator**, **researcher**, **analyst**), each with a focused toolset and
  its own free model. Specialist progress streams live to the CLI and dashboard.
- **Reason and act in a loop** — JARVIS plans, calls tools, observes results,
  and repeats until your request is done (OpenAI-style function calling).
- **Never get stuck on a rate limit** — all configured providers form a
  fallback chain; when one free tier throttles, JARVIS transparently switches
  to the next.
- **Runs autonomously** — by default JARVIS acts without asking permission for
  every step, so it builds whole deliverables end to end. Only a tiny accident
  guard (catastrophic commands like `rm -rf /`) still stops it. Flip
  `JARVIS_REQUIRE_CONFIRMATION=true` if you'd rather approve each action.
- **Build finished, professionally-styled deliverables** — `create_pptx`
  (PowerPoint decks with a colored title slide, accent bars, and footer page
  numbers — not PowerPoint's bland default template), `create_pdf` (reports,
  study materials, handouts with a themed header/footer and accent rule), and
  `create_website` (complete multi-page static sites with shared nav +
  responsive CSS). `create_pptx`/`create_pdf` take a `theme`
  (`professional`, `modern`, `dark`, `minimal`); `create_website` takes a
  `theme` too — `futuristic` (default: dark glassmorphism + neon-cyan accents
  matching the dashboard), `clean`, `dark`, or `minimal`.
- **Control the PC** — run commands, read/write files, move the mouse, type,
  press hotkeys, take screenshots, manage the clipboard, launch & focus apps.
- **See the screen** — `see_screen` screenshots and describes the UI with a
  free vision model, so JARVIS can act on what's actually there.
- **Remember across sessions** — `remember`/`recall` persist facts and
  preferences in a local SQLite store (free, offline).
- **Talk, hands-free** — optional offline voice in/out (`--voice`), plus a
  wake-word loop (`--wake`): just say *"JARVIS, …"*. No cloud key needed.
- **Schedule work** — `schedule_task` runs prompts later or on a repeat
  (*"every 30 minutes"*, *"at 14:30"*); results are logged.
- **Web dashboard** — `--dashboard` serves a local page to drive JARVIS and
  watch its tool calls live (stdlib only, no web framework).
- **Use other AIs as tools** — `ask_model` routes a subtask to any configured
  backend: API models, or Gemini/ChatGPT driven in a browser.
- **Stay safe** — every dangerous action (shell, writes, clicks, keystrokes,
  launches) passes through a confirmation gate with a hard blocklist.

---

## Architecture

```
jarvis/
  agents/           multi-agent team: specialist specs + builder
                    (coder · operator · researcher · analyst)
  providers/        OpenAI-compatible client + per-provider registry
                    (groq, cerebras, mistral, nvidia)
    providers/router.py  fallback chain across all free providers
  tools/            the things JARVIS can DO
                    filesystem · shell · system_info · pc_control · apps
                    · documents (create_pptx / create_pdf / create_website)
                    · ai_delegate (ask_model) · vision (see_screen)
                    · memory_tools (remember/recall) · scheduler_tools
                    · agent_tools (delegate_to_agent / delegate_parallel)
  integrations/
    web/            Gemini & ChatGPT via Playwright (persistent login)
    desktop/        Claude desktop & Cursor via window focus + keyboard
  core/             agent loop · memory · longterm (SQLite) · config · prompts
  scheduler.py      run tasks later / on a repeat (stdlib threads)
  dashboard.py      local web UI to drive & watch JARVIS (stdlib http.server)
  voice.py          optional offline TTS/STT + wake-word loop
  utils/            logging · safety gate
  app.py            wires config + providers + tools into an Agent
  cli.py            interactive REPL / one-shot mode
```

All four API providers speak the same OpenAI `/chat/completions` dialect, so they
share **one** client (`OpenAICompatibleProvider`) parameterised by base URL,
key, and model. Add another OpenAI-compatible provider by adding one entry to
`PROVIDER_SPECS` in `jarvis/providers/registry.py`.

### Multi-agent team

JARVIS runs as a **lead orchestrator + specialists**. The lead handles simple
requests itself; for complex, multi-part jobs it decomposes the work and calls
`delegate_to_agent` to hand pieces to the right specialist, then synthesizes the
results. Each specialist is a full agent with its own loop, a **focused subset
of tools**, and a **preferred free model** (so load spreads across providers):

| Agent | Good at | Tools | Default model |
|-------|---------|-------|---------------|
| `planner` | step-by-step plans | none (pure reasoning) | Mistral |
| `coder` | code, files, shell | filesystem + `run_command` | NVIDIA Nemotron |
| `operator` | GUI control | screen/click/type/apps + vision | Groq |
| `researcher` | gathering info | `ask_model` (Gemini/ChatGPT) + memory | Groq |
| `analyst` | diagnosis | vision + system/process info | Cerebras |

For a complex goal the lead first asks `planner` for a numbered plan, then
delegates each step to the right specialist and synthesizes the results.
Independent steps run **concurrently** via `delegate_parallel` — each on its own
specialist and model — so they finish in the time of the slowest, not the sum.
As specialists work, their tool calls stream live to the CLI feed and the web
dashboard (tagged like `coder:run_command`).

Specialists can't re-delegate (no infinite loops), and each provider chain
falls back to the others if its preferred model is rate-limited. Edit the roster
in `jarvis/agents/specs.py`. If a provider isn't configured, that agent falls
back to the default brain; a spec that asks for tools none of which exist is
skipped, but a tool-less spec (the planner) is kept as a pure-reasoning agent.

---

## Setup

### Windows (turnkey)

```bat
setup.bat        :: one-time: venv + install + browser + seeds .env
:: then edit .env, paste in a free API key (Groq is easiest), and:
run.bat          :: interactive   (run.bat --wake / --voice / --dashboard)
```

### Manual (any OS)

```bash
# 1. Install
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[all]"                            # core + pc + web + documents
playwright install chromium                        # for Gemini/ChatGPT web
# document builders only: pip install -e ".[documents]"  (python-pptx + reportlab)

# 2. Configure keys
cp .env.example .env        # then edit .env and fill in the keys you have
```

You only need a key for **at least one** provider. Get free keys from:

| Provider | Where | Free model (default) |
|----------|-------|----------------------|
| Groq     | console.groq.com        | `llama-3.3-70b-versatile` |
| Cerebras | cloud.cerebras.ai       | `gpt-oss-120b` |
| Mistral  | console.mistral.ai      | `mistral-small-latest` |
| NVIDIA   | build.nvidia.com        | `nvidia/nemotron-3-super-120b-a12b` |

Set `JARVIS_DEFAULT_PROVIDER` in `.env` to pick the reasoning brain.

---

## Usage

```bash
# Interactive
python -m jarvis

# One-shot
python -m jarvis "take a screenshot and tell me what's on screen"
python -m jarvis "ask gemini for 3 dinner ideas, then save them to notes.txt"

# Skip browser backends (no Gemini/ChatGPT, faster startup)
python -m jarvis --no-web

# Voice mode (free TTS/STT — needs the `voice` extra + a microphone)
pip install -e ".[voice]"      # for fully offline STT also: pip install pocketsphinx
python -m jarvis.voice "test"  # verify talkback first (speaks two sentences)
python -m jarvis --voice

# Hands-free wake word — say "JARVIS, ..." to issue commands
python -m jarvis --wake

# Local web dashboard — open http://127.0.0.1:8765 to drive & watch JARVIS
python -m jarvis --dashboard
```

Scheduling works through normal conversation, e.g. *"every morning at 09:00,
summarize my unread emails"* → JARVIS calls `schedule_task`; results land in
`~/.jarvis/scheduled.log`.

Inside the loop, JARVIS decides which tools to call. Examples:

- *"make a 5-slide deck on our Q2 results"* → `create_pptx`
- *"turn these notes into a study-guide PDF"* → `create_pdf`
- *"build me a portfolio website with home + about pages"* → `create_website`
- *"open Cursor and create a new Python file"* → `open_app` + PC control
- *"what's eating my CPU?"* → `list_processes`
- *"ask chatgpt to explain X, then summarize it for me"* → `ask_model` (web)
- *"clean up *.tmp in Downloads"* → `run_command`

---

## Autonomy & safety

JARVIS is **autonomous by default** (`JARVIS_REQUIRE_CONFIRMATION=false`): it
runs shell commands, writes files, drives the PC, and builds decks/PDFs/sites
without stopping to ask, so it can finish multi-step jobs on its own. The only
remaining guard is a small **hard blocklist** of catastrophic, irreversible
commands (`rm -rf /`, fork bombs, `mkfs`, `format c:`, …) that exists to catch a
model accidentally emitting something machine-destroying.

- Want to approve each action? Set `JARVIS_REQUIRE_CONFIRMATION=true`.
- Want zero guards at all? Set `JARVIS_DISABLE_BLOCKLIST=true` (not recommended —
  this removes even the catastrophic-command guard).

---

## Honest limitations

- **Web automation is brittle.** Gemini/ChatGPT have no public free chat API, so
  JARVIS drives them in a browser. Their HTML changes often — the selectors in
  `integrations/web/*.py` may need occasional updates. You log in once in the
  launched browser window (a persistent profile keeps you signed in).
- **Desktop Claude/Cursor have no text-out.** `integrations/desktop` can launch,
  focus, and type into them, but it can't reliably read their replies back as
  text. Prefer the API/web backends when you need the answer programmatically.
- **PC control needs a real desktop session.** `pyautogui`/`pygetwindow` won't
  work over a headless/SSH session without a display.

---

## Development

```bash
pip install -e ".[all]" pytest
pytest -q          # headless smoke tests (no keys/desktop needed)
```

The package is import-safe without the optional GUI/browser deps, so the core
and provider layers can be tested and used on a server.
