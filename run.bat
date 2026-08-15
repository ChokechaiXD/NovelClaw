@echo off
setlocal
cd /d "%~dp0"

if not exist "novelclaw.exe" (
    echo [*] Compiling NovelClaw Go binary...
    go build -ldflags="-s -w" -o novelclaw.exe .
)

echo [*] Starting NovelClaw...
novelclaw.exe -port 4173
