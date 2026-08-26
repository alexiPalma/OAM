"""OAM master launcher.

The runtime patches must be loaded before fix.py so admin UI, keyword
navigation, promo UI and the battle runtime all use the intended handlers.
"""
import asyncio

from battle_sanity import check_combat_engine

# Promo UI is routed through run.py because fix.py registers run.callback and
# run.text_handler as the actual dispatcher handlers.
import admin_runtime
import top_ui_patch
import keyword_runtime_patch
import promo_bridge

from fix import main

# Direct /атаковать @username support patches fix.text_handler after fix is
# loaded and before fix.main registers the dispatcher handler.
import attack_command_patch


if __name__ == "__main__":
    check_combat_engine()
    print("[OAM] COMBAT SANITY CHECK: OK")
    print("[OAM] ADMIN PROMO UI: OK")
    print("[OAM] PROMO ROUTING: OK")
    print("[OAM] KEYWORD NAVIGATION: OK")
    print("[OAM] DIRECT ATTACK COMMAND: OK")
    print("[OAM] AUTHORITATIVE RUNTIME: fix.py")
    asyncio.run(main())
