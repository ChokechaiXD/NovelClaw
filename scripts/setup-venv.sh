#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH=
unset VIRTUAL_ENV || true

if [ -x .venv312/Scripts/python.exe ] || [ -x .venv312/bin/python ]; then
    echo ".venv312 already exists, skipping creation."
else
    if command -v uv >/dev/null 2>&1; then
        echo "Creating venv with uv..."
        uv venv .venv312 --python 3.12
    else
        echo "Creating venv with python -m venv..."
        python3 -m venv .venv312
    fi
fi

PY="$PWD/.venv312/bin/python"
[ -x "$PY" ] || PY="$PWD/.venv312/Scripts/python.exe"

if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PY" pydantic pyyaml jsonschema pytest pytest-asyncio
else
    "$PY" -m pip install pydantic pyyaml jsonschema pytest pytest-asyncio
fi

cat <<EOF

Venv ready. Run tests:
    $PY -m pytest tests/ -q

EOF
