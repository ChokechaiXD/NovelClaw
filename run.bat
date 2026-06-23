@echo off
cd /d "%~dp0"
title NovelClaw
chcp 65001 >nul

:: ── Config ──────────────────────────────────────────────────────
set PORT=4173
set HOST=127.0.0.1

echo ╔══════════════════════════════════════════════════════════╗
echo ║                    NovelClaw                            ║
║           Chinese → Thai Translation Toolkit           ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo  📖 Reader:     http://localhost:%PORT%/
echo  📋 Dashboard:  http://localhost:%PORT%/#admin/jobs
echo  📊 Report:     python tools\novelctl.py report
echo  🔍 Check:      python tools\novelctl.py check
echo  ⚡ Translate:  python tools\novelctl.py translate ^<range^>
echo  🛠  Rebuild:    python tools\novelctl.py rebuild
echo.
echo ══════════════════════════════════════════════════════════════
echo  LAN access: set HOST=0.0.0.0 + ADMIN_TOKEN=***
echo ══════════════════════════════════════════════════════════════
echo.

cd reader
echo ✅ กำลังเริ่ม NovelClaw Reader ที่ http://localhost:%PORT% ...
echo.
node server.js
if errorlevel 1 (
    echo.
    echo ❌ เซิร์ฟเวอร์มีปัญหา ลอง npm install ก่อน?
    pause
)
