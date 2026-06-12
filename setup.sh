#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=============================="
echo " SpotDL GUI - Setup (Linux/macOS)"
echo "=============================="

# --- Check Python ---
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3 not found. Install it first:"
    echo "  Arch:  sudo pacman -S python"
    echo "  Debian:sudo apt install python3"
    echo "  macOS: brew install python3"
    exit 1
fi

echo "[1/3] Creating virtual environment..."
"$PYTHON" -m venv venv
source venv/bin/activate

echo "[2/3] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt

echo "[3/3] Making launcher executable..."
chmod +x start.sh

echo ""
echo " Done!"
echo ""
echo "To run the app:"
echo "  ./start.sh"
echo ""
echo "(Or double-click start.sh in your file manager)"
