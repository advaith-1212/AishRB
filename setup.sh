#!/usr/bin/env bash
set -e

echo "=== Resume Builder Setup ==="
echo ""

# 1. Install WeasyPrint system dependencies
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ">> macOS detected. Installing WeasyPrint dependencies via Homebrew..."
    if ! command -v brew &>/dev/null; then
        echo "ERROR: Homebrew not found. Install it from https://brew.sh"
        exit 1
    fi
    brew install cairo pango gdk-pixbuf libffi 2>/dev/null || true
elif [[ -f /etc/debian_version ]]; then
    echo ">> Debian/Ubuntu detected. Installing WeasyPrint dependencies via apt..."
    sudo apt-get update && sudo apt-get install -y \
        libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev
else
    echo ">> Unknown OS. You may need to install WeasyPrint dependencies manually."
    echo "   See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
fi

echo ""

# 2. Create Python virtual environment
if [ ! -d "venv" ]; then
    echo ">> Creating Python virtual environment..."
    python3 -m venv venv
fi

# 3. Install Python dependencies
source venv/bin/activate
echo ">> Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "============================================"
echo "  Setup complete!"
echo ""
echo "  Start the app:"
echo "    source venv/bin/activate"
echo "    python3 local_app.py"
echo ""
echo "  Then open http://127.0.0.1:5001"
echo "============================================"
