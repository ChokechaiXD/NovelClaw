@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title NovelClaw Reader

:: Get local IP for LAN access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address" /c:"IPv4"') do (
  for /f "tokens=*" %%b in ("%%a") do (
    if not defined LOCAL_IP set "LOCAL_IP=%%b"
  )
)
if not defined LOCAL_IP set LOCAL_IP=127.0.0.1

:: Kill old process on port 4173
for /f "tokens=5" %%a in ('netstat -ano ^| find ":4173" ^| find "LISTENING"') do (
  taskkill /F /PID %%a >nul 2>&1
)

:: Kill any lingering node.exe from NovelClaw
taskkill /F /FI "WINDOWTITLE eq node.exe*NovelClaw*" /IM node.exe >nul 2>&1

:: Start server
cd /d "%~dp0reader"
start /B node server.js >nul 2>&1

cls
echo.
echo  ╔══════════════════════════════════════╗
echo  ║       🦀 NovelClaw Reader            ║
echo  ║                                      ║
echo  ║   โปรแกรมอ่านนิยายแปลไทย            ║
echo  ║                                      ║
echo  ║   📱 http://%LOCAL_IP%:4173          ║
echo  ║   💻 http://localhost:4173           ║
echo  ║                                      ║
echo  ║   [Enter] = เปิดเบราว์เซอร์          ║
echo  ║   [X] แล ะ Enter = ปิดและออก        ║
echo  ╚══════════════════════════════════════╝
echo.

:: Auto-open browser
start http://localhost:4173

:loop
set /p input="> "
if /i "%input%"=="x" goto :exit
if /i "%input%"=="exit" goto :exit
start http://localhost:4173
goto :loop

:exit
echo.
echo  กำลังปิดเซิร์ฟเวอร์...
taskkill /F /IM node.exe >nul 2>&1
echo  ปิดเรียบร้อย ขอบคุณที่ใช้ NovelClaw ค่ะ 🦀
timeout /t 2 >nul
