"""Compatibility launcher.

The real runtime is centralized in fix.py. Keeping this wrapper means older
Pterodactyl start commands that point at fixed_launcher.py also get exactly the
same callback registration and synchronized battle implementation.
"""
import asyncio
from fix import main


if __name__ == "__main__":
    asyncio.run(main())
