@echo off
setlocal
REM ── JARVIS one-time setup for Windows ───────────────────────────────────────
REM Creates a virtual environment, installs JARVIS with all free extras,
REM downloads the browser for Gemini/ChatGPT automation, and seeds your .env.

cd /d "%~dp0"
echo === JARVIS setup ===
echo Working in: %cd%

where python >nul 2>nul
if errorlevel 1 (
  echo [!] Python not found on PATH. Install Python 3.10+ from python.org and re-run.
  echo     During install, check "Add python.exe to PATH".
  goto :fail
)

echo [1/4] Creating virtual environment ^(.venv^)...
python -m venv .venv
if errorlevel 1 (
  echo [!] Failed to create the virtual environment.
  goto :fail
)

echo [2/4] Installing JARVIS + all free extras...
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [!] Failed to activate the virtual environment.
  goto :fail
)
python -m pip install --upgrade pip >nul
pip install -e ".[all]"
if errorlevel 1 (
  echo [!] Failed to install dependencies. Scroll up for the pip error.
  goto :fail
)

echo [3/4] Installing Chromium for browser automation...
python -m playwright install chromium
if errorlevel 1 (
  echo [!] Chromium install failed ^(non-fatal — Gemini/ChatGPT browser features
  echo     won't work, but the rest of JARVIS will^). Continuing...
)

echo [4/4] Preparing your .env config...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo     Created .env  --  open it and add at least one free API key ^(Groq is easiest^).
) else (
  echo     .env already exists, leaving it as-is.
)

echo.
echo === Setup complete ===
echo  1. Edit .env and paste in your free API key^(s^).
echo  2. Verify voice talkback:   python -m jarvis.voice "test"
echo  3. Run JARVIS:              run.bat        ^(or: python -m jarvis^)
echo.
pause
exit /b 0

:fail
echo.
echo Setup did not finish. See the message above for what to fix, then re-run setup.bat.
echo.
pause
exit /b 1
