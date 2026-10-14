#!/bin/bash
# Double-click in Finder: activates .venv and starts backend + dashboard, then opens the browser.
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
  python run.py
else
  echo ".venv bulunamadı, sistem python3 kullanılıyor."
  python3 run.py
fi
