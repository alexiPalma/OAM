"""OAM master launcher.

All runtime fixes are loaded through fix.py so the Pterodactyl/Windows
working launcher cannot accidentally use the old callback registration path.
"""
import asyncio
from fix import main


if __name__ == "__main__":
    asyncio.run(main())
