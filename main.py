"""Shortcut so `python main.py` from the project root starts the Master Agent (master/main.py)."""
import runpy
import sys
from pathlib import Path

MASTER_DIR = Path(__file__).resolve().parent / "master"

if __name__ == "__main__":
    sys.path.insert(0, str(MASTER_DIR))
    runpy.run_path(str(MASTER_DIR / "main.py"), run_name="__main__")
