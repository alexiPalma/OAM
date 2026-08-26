"""OAM deterministic entrypoint.

The previous launcher wrapped callbacks in several layers. This entrypoint
imports the real application once, installs the battle implementation before
Dispatcher registers callbacks, and then starts the existing run.main().
"""
import asyncio

import run
import bot as app
import battle_force_sync

# These assignments happen before run.main() creates the Dispatcher and before
# its callback handler starts receiving updates.
app.battle_confirm = battle_force_sync.confirm
app.battle_accept = battle_force_sync.accept
app.battle_decline = battle_force_sync.decline

print('[OAM] battle runtime installed: synchronized accept/confirm')

if __name__ == '__main__':
    asyncio.run(run.main())
