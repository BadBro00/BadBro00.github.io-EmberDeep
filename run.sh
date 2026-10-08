#!/bin/sh
# Run EMBERDEEP from source (creates venv on first run).
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
fi
.venv/bin/python game.py
