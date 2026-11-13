#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PHANTOM_PYTHON="${PHANTOM_PYTHON:-/data/data/com.termux/files/usr/tmp/phantomgpt-venv/bin/python}"
if [ ! -x "$PHANTOM_PYTHON" ]; then
  echo "Python environment missing; see README.md for setup." >&2
  exit 1
fi
PHANTOM_LIB=/data/data/com.termux/files/usr/tmp/phantomgpt-runtime/data/data/com.termux/files/usr/lib
if [ -d "$PHANTOM_LIB" ]; then
  export LD_LIBRARY_PATH="$PHANTOM_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
exec "$PHANTOM_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8000}" --loop asyncio --http h11
