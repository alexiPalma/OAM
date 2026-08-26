"""OAM battle launcher."""
import asyncio
import run
import bot as app
import battle_force_sync

_original_run_callback = run.callback
app.battle_confirm = battle_force_sync.confirm
app.battle_accept = battle_force_sync.accept
app.battle_decline = battle_force_sync.decline

async def _battle_callback(c, bot):
    data = c.data or ''
    if data == 'battle_confirm':
        return await battle_force_sync.confirm(c, bot)
    if data.startswith('accept:'):
        try:
            attacker_id = int(data.split(':', 1)[1])
        except (ValueError, TypeError):
            return await c.answer('Некорректный запрос боя.', show_alert=True)
        return await battle_force_sync.accept(c, attacker_id, bot)
    if data.startswith('decline:'):
        try:
            attacker_id = int(data.split(':', 1)[1])
        except (ValueError, TypeError):
            return await c.answer('Некорректный запрос боя.', show_alert=True)
        return await battle_force_sync.decline(c, attacker_id, bot)
    return await _original_run_callback(c, bot)

# This is the callback that run.main() actually registers in Dispatcher.
run.callback = _battle_callback

print('[OAM] DIRECT BATTLE CALLBACK ACTIVE')
print('[OAM] attacker + defender use the same animation coroutine/clock')

if __name__ == '__main__':
    asyncio.run(run.main())
