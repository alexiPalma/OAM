"""OAM master launcher.

The runtime patches are loaded in the same order as the authoritative
fix.py dispatcher. Callback safety is installed AFTER fix.py is imported so
it wraps the exact callback function that the dispatcher will register.
"""
import asyncio

from battle_sanity import check_combat_engine

# Patches that must exist before fix.py creates its runtime wrappers.
import admin_runtime
import top_ui_patch
import keyword_runtime_patch
import promo_bridge
import promo_command_patch
import callback_compat_patch

from fix import main

# Patches that wrap the authoritative fix.py handlers.
import callback_guard
import attack_command_patch


if __name__ == "__main__":
    check_combat_engine()
    print("[OAM] COMBAT SANITY CHECK: OK")
    print("[OAM] ADMIN PROMO UI: OK")
    print("[OAM] PROMO ROUTING: OK")
    print("[OAM] TWO-STEP PROMO INPUT: OK")
    print("[OAM] KEYWORD NAVIGATION: OK")
    print("[OAM] CALLBACK COMPATIBILITY: OK")
    print("[OAM] CALLBACK GUARD: OK")
    print("[OAM] DIRECT ATTACK COMMAND: OK")
    print("[OAM] AUTHORITATIVE RUNTIME: fix.py")
    asyncio.run(main())
