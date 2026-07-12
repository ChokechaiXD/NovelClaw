@echo off
chcp 65001 >nul 2>&1
setlocal
title NovelClaw Reader

if not defined HOST set "HOST=0.0.0.0"
if not defined PORT set "PORT=4173"
if not defined TRUSTED_LAN set "TRUSTED_LAN=true"
if not defined NOVELCLAW_RUN_OPEN set "NOVELCLAW_RUN_OPEN=1"

set "ROOT_DIR=%~dp0"
set "READER_DIR=%~dp0reader"
set "HEALTH_URL=http://127.0.0.1:%PORT%/api/health"
set "SERVER_PID="
set "SERVER_REUSED=0"

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address" /c:"IPv4"') do (
  for /f "tokens=*" %%b in ("%%a") do if not defined LOCAL_IP set "LOCAL_IP=%%b"
)
if not defined LOCAL_IP set "LOCAL_IP=127.0.0.1"

rem Reuse a healthy NovelClaw instance. Never kill an unrelated process.
powershell.exe -NoProfile -Command "try { $h=Invoke-RestMethod -Uri '%HEALTH_URL%' -TimeoutSec 2; if ($h.service -eq 'novelclaw-reader') { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 (
  set "SERVER_REUSED=1"
  goto ready
)

rem Start one hidden Node process and keep its PID for targeted shutdown.
for /f "delims=" %%P in ('powershell.exe -NoProfile -Command "(Start-Process -FilePath 'node' -ArgumentList 'server.js' -WorkingDirectory '%READER_DIR%' -WindowStyle Hidden -PassThru).Id"') do set "SERVER_PID=%%P"
if not defined SERVER_PID goto start_failed

rem Wait until the API is ready before opening the browser.
powershell.exe -NoProfile -Command "$deadline=(Get-Date).AddSeconds(15); do { try { $h=Invoke-RestMethod -Uri '%HEALTH_URL%' -TimeoutSec 1; if ($h.service -eq 'novelclaw-reader') { exit 0 } } catch {}; Start-Sleep -Milliseconds 250 } while ((Get-Date) -lt $deadline); exit 1" >nul 2>&1
if errorlevel 1 goto start_failed

:ready
cls
echo.
echo  NovelClaw Reader is ready
echo.
echo  PC:  http://localhost:%PORT%
echo  LAN: http://%LOCAL_IP%:%PORT%
echo.
if "%SERVER_REUSED%"=="1" echo  Reusing the reader process that is already running.
echo  Press Enter to open the reader, or type X and press Enter to close.
echo.

if not "%NOVELCLAW_RUN_OPEN%"=="0" start "" "http://localhost:%PORT%"

:loop
set "input="
set /p "input=> "
if /i "%input%"=="x" goto exit
if /i "%input%"=="exit" goto exit
start "" "http://localhost:%PORT%"
goto loop

:start_failed
if defined SERVER_PID taskkill /PID %SERVER_PID% /T /F >nul 2>&1
echo.
echo  NovelClaw Reader could not start on port %PORT%.
echo  Check that Node.js is installed and the port is available.
pause
exit /b 1

:exit
if "%SERVER_REUSED%"=="1" (
  echo  The existing reader process was left running.
) else if defined SERVER_PID (
  taskkill /PID %SERVER_PID% /T /F >nul 2>&1
  echo  NovelClaw Reader stopped.
)
exit /b 0
