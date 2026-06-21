@echo off
setlocal
REM ── Launch JARVIS ───────────────────────────────────────────────────────────
REM Usage:
REM   run.bat                 interactive assistant
REM   run.bat --wake          hands-free wake word ("JARVIS, ...")
REM   run.bat --voice         voice in + talkback
REM   run.bat --dashboard     local web UI at http://127.0.0.1:8765
REM   run.bat "do something"  one-shot command

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo [!] No virtual environment found here: %cd%\.venv
  echo     Run setup.bat first ^(double-click it, or run it from this folder^).
  goto :fail
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [!] Could not activate the virtual environment. Try deleting the
  echo     .venv folder and running setup.bat again.
  goto :fail
)

if not exist ".env" (
  echo [!] No .env file found here: %cd%\.env
  echo     Run setup.bat first, or copy .env.example to .env and add an API key.
  goto :fail
)

python -m jarvis %*
if errorlevel 1 (
  echo.
  echo [!] JARVIS exited with an error ^(see above^). Common causes:
  echo     - No API key set in .env ^(open .env and add at least one, e.g. GROQ_API_KEY^)
  echo     - Missing dependencies ^(re-run setup.bat^)
  goto :fail
)

goto :eof

:fail
echo.
pause
exit /b 1
