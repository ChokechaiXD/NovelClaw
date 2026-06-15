@echo off
cd /d "%~dp0\reader"
start http://localhost:4173
node server.js
