"""OAM master launcher.

Always starts fix.py, never run.py/bot.py directly.  A combat sanity check
runs before polling so a stale/broken combat engine cannot silently start.
"""
import asyncio

from battle_sanity import check_combat_engine
from fix import main


if __name__ == "__main__":
    check_combat_engine()
    print("[OAM] COMBAT SANITY CHECK: OK")
    print("[OAM] AUTHORITATIVE RUNTIME: fix.py")
    asyncio.run(main())
