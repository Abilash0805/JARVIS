@echo off
REM ── Launch JARVIS ───────────────────────────────────────────────────────────
REM Usage:
REM   run.bat                 interactive assistant
REM   run.bat --wake          hands-free wake word ("JARVIS, ...")
REM   run.bat --voice         voice in + talkback
REM   run.bat --dashboard     local web UI at http://127.0.0.1:8765
REM   run.bat "do something"  one-shot command

if not exist ".venv\Scripts\activate.bat" (
  echo [!] No virtual environment found. Run setup.bat first.
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m jarvis %*
