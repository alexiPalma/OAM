"""OAM master launcher.

Always starts fix.py, never run.py/bot.py directly.  Runtime UI/keyword
patches are loaded before the authoritative battle runtime.
"""
import asyncio

from battle_sanity import check_combat_engine
import top_ui_patch
import keyword_runtime_patch
from fix import main


if __name__ == "__main__":
    check_combat_engine()
    print("[OAM] COMBAT SANITY CHECK: OK")
    print("[OAM] AUTHORITATIVE RUNTIME: fix.py")
    print("[OAM] KEYWORD NAVIGATION: OK")
    asyncio.run(main())
