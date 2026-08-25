"""Reliable launcher for the WorldWarDynasty bot.

This launcher explicitly loads the repository's sitecustomize fixes and then
starts run.py. It avoids the broken indentation from the previous launcher.
"""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load the permanent compatibility/feature patches before run.py starts.
try:
    import sitecustomize  # noqa: F401
except Exception as exc:
    print(f"Warning: sitecustomize.py could not be loaded: {exc}")

runpy.run_path(str(ROOT / "run.py"), run_name="__main__")
