#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -x "$ROOT/.venv/bin/python" ]; then
    command -v uv >/dev/null || { echo "uv is needed: https://docs.astral.sh/uv/"; exit 1; }
    uv venv -q "$ROOT/.venv" && uv pip install -q --python "$ROOT/.venv/bin/python" pillow pygments ruff
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$ROOT/.venv/bin/python" -m codememe.cli "$@"
