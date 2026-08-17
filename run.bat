@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Building...
go build -ldflags="-s -w" -o novelclaw.exe . || echo [WARN] build failed - using existing exe

echo [2/3] Checking port 4173...
netstat -ano | findstr /r ":4173 .*LISTENING" >nul && (
    echo [WARN] Port 4173 already in use - server may be running elsewhere!
    echo        Close the existing process first, then run this again.
    pause
    exit /b 1
)

echo [3/3] Starting server...
novelclaw.exe -port 4173