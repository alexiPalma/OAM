"""OAM master launcher.

The runtime patches must be loaded before fix.py so admin UI, keyword
navigation and the battle runtime all use the same patched handlers.
"""
import asyncio

from battle_sanity import check_combat_engine

# IMPORTANT: admin_runtime replaces bot's admin/callback handlers with the
# full button-based promo-code UI. It must be imported before fix.py starts
# the dispatcher, otherwise the old text-only promo menu remains active.
import admin_runtime
import top_ui_patch
import keyword_runtime_patch

from fix import main


if __name__ == "__main__":
    check_combat_engine()
    print("[OAM] COMBAT SANITY CHECK: OK")
    print("[OAM] ADMIN PROMO UI: OK")
    print("[OAM] KEYWORD NAVIGATION: OK")
    print("[OAM] AUTHORITATIVE RUNTIME: fix.py")
    asyncio.run(main())
