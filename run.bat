@echo off
setlocal

REM ============================================================
REM  NovelClaw Reader — Windows launcher
REM
REM  - Kills anything on port 4173 first (avoids EADDRINUSE)
REM  - Starts the reader in the foreground
REM  - Closing this window (or Ctrl+C) kills the server
REM
REM  Place this at the root of the NovelClaw project.
REM  Double-click or run from any terminal.
REM ============================================================

cd /d "%~dp0reader"

echo.
echo === NovelClaw Reader ===
echo.

REM --- Kill any process bound to port 4173 ---
echo Cleaning up port 4173...
set "KILLED=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr :4173 ^| findstr LISTENING 2^>nul') do (
    echo   killing PID %%P
    taskkill /F /PID %%P >nul 2>&1
    set "KILLED=1"
)
if "%KILLED%"=="0" echo   (port 4173 was free)

echo.
echo Starting server...
echo.
echo   Open  http://localhost:4173/  in your browser
echo.
echo   Press Ctrl+C to stop, or close this window.
echo   (Closing the window kills the server immediately.)
echo.

REM --- Start server in foreground ---
REM The node process is bound to this terminal.
REM When the terminal/window closes, Windows sends a kill signal
REM to all child processes — so the server dies with the window.
node server.js

REM If node exits cleanly, this script also exits.
endlocal
