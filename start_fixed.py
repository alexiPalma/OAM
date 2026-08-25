"""Pterodactyl launcher for WorldWarDynasty.

This file deliberately contains no bot logic. It replaces itself with run.py,
so Pterodactyl executes the real application exactly as `python run.py` does.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT / "run.py"

if not RUN.is_file():
    raise FileNotFoundError(f"run.py not found: {RUN}")

os.chdir(ROOT)
os.execv(sys.executable, [sys.executable, str(RUN)])
