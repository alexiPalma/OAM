"""Compatibility launcher for OAM.

Use fixed_launcher.py for the real Dispatcher registration. Keeping this file
as a thin wrapper prevents the old monkey-patching callback path from being
used accidentally.
"""
import asyncio
from fixed_launcher import main


if __name__ == "__main__":
    asyncio.run(main())
