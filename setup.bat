@echo off
REM ── JARVIS one-time setup for Windows ───────────────────────────────────────
REM Creates a virtual environment, installs JARVIS with all free extras,
REM downloads the browser for Gemini/ChatGPT automation, and seeds your .env.

echo === JARVIS setup ===

where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python not found on PATH. Install Python 3.10+ from python.org and re-run.
  exit /b 1
)

echo [1/4] Creating virtual environment (.venv)...
python -m venv .venv || exit /b 1

echo [2/4] Installing JARVIS + all free extras...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -e ".[all]" || exit /b 1

echo [3/4] Installing Chromium for browser automation...
python -m playwright install chromium

echo [4/4] Preparing your .env config...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo     Created .env  --  open it and add at least one free API key (Groq is easiest).
) else (
  echo     .env already exists, leaving it as-is.
)

echo.
echo === Setup complete ===
echo  1. Edit .env and paste in your free API key(s).
echo  2. Verify voice talkback:   python -m jarvis.voice "test"
echo  3. Run JARVIS:              run.bat        (or: python -m jarvis)
echo.
pause
