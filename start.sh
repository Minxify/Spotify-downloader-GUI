#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$DIR/venv/bin:$PATH"
if [ ! -f "$DIR/venv/bin/python" ]; then
    echo "Venv not found! Run setup.sh first."
    exit 1
fi
exec "$DIR/venv/bin/python" "$DIR/SpDL.py" "$@"
