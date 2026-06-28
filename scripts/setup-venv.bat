@echo off
REM ── NovelClaw venv setup for Windows ────────────────────────────────
REM Usage: scripts\setup-venv.bat
REM Requires: Python 3.12 on PATH, OR uv installed (preferred).
REM
REM Old setup used `python -m venv` which produced a broken venv on
REM machines where a global Python venv was on PATH (it poisoned sys.path even
REM in isolated venvs via the inherited PYTHONPATH env var).
REM This script uses `uv venv` instead — uv clears the inherited env and
REM installs packages via `uv pip`, which respects venv isolation.

setlocal

cd /d "%~dp0\.."

set PYTHONPATH=
set VIRTUAL_ENV=

if exist .venv312\Scripts\python.exe (
    echo .venv312 already exists, skipping creation.
    goto :install
)

where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    echo Creating venv with uv...
    uv venv .venv312 --python 3.12
    if errorlevel 1 (
        echo uv venv failed, falling back to python -m venv.
        echo If that fails too, see README "Troubleshooting".
        python -m venv .venv312
    )
) else (
    echo Creating venv with python -m venv...
    python -m venv .venv312
)

:install
echo Installing test dependencies...
where uv >nul 2>nul
if %ERRORLEVEL%==0 (
    uv pip install --python .venv312\Scripts\python.exe pydantic pyyaml jsonschema pytest pytest-asyncio
) else (
    .venv312\Scripts\python.exe -m pip install pydantic pyyaml jsonschema pytest pytest-asyncio
)

echo.
echo Venv ready. Run tests:
echo     .venv312\Scripts\python.exe -m pytest tests/ -q
echo.
endlocal
