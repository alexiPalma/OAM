"""WorldWarDynasty final runtime bootstrap.

Loaded by Python before the launcher. Battle handlers are patched at import
 time, before working_launcher registers its callback observer.
"""
import asyncio
import functools
import sys

# IMPORTANT: this is deliberately done at Python startup. The launcher later
# registers callback handlers, so changing functions only from asyncio.run()
# is too late for some launcher variants.
try:
    import battle_rules_patch
except Exception as exc:
    print(f'[WorldWarDynasty] battle patch import warning: {exc}')

try:
    import bot as _app
    import battle_force_sync as _force_battle
    _app.battle_confirm = _force_battle.confirm
    _app.battle_accept = _force_battle.accept
    print('[WorldWarDynasty] direct battle sync installed')
except Exception as exc:
    print(f'[WorldWarDynasty] direct battle sync warning: {exc}')

_ORIGINAL_ASYNCIO_RUN = asyncio.run


def _finalize():
    try:
        import config
        import bot as app
        import battle_rules_patch
        main = sys.modules.get('__main__')
        if main is None:
            return

        # Keep the direct battle handler authoritative. The older patch remains
        # available for compatibility, but must not replace the force handler.
        if '_force_battle' in globals():
            app.battle_confirm = _force_battle.confirm
            app.battle_accept = _force_battle.accept
        else:
            battle_rules_patch.install(app)

        if not hasattr(main, 'case') and hasattr(app, 'case'):
            main.case = app.case
        patcher = getattr(config, '_patch_run', None)
        if patcher:
            patcher(main)

        _install_admin_commands(main)
        _install_achievement_guard()
    except Exception as exc:
        print(f'[WorldWarDynasty] final bootstrap warning: {exc}')


def _install_achievement_guard():
    try:
        import achievements
        achievements.REQ_KEYS = (
            'kill_soldier', 'kill_drone', 'kill_tank', 'kill_bmp',
            'kill_artillery', 'kill_helicopter', 'kill_plane', 'kill_missile',
            'kill_interceptor',
        )
        achievements.REQ_NAMES = (
            '💀 Уничтожено солдат', '💀 Уничтожено БПЛА',
            '💀 Уничтожено танков', '💀 Уничтожено БМП',
            '💥 Уничтожено артиллерии', '💀 Уничтожено вертолётов',
            '💀 Уничтожено самолётов', '💀 Уничтожено ракет',
            '💀 Уничтожено перехватчиков',
        )
    except Exception:
        pass


def _install_admin_commands(run):
    if getattr(run, '_wwd_admin_commands_final', False):
        return
    import bot as app
    from config import UNITS
    from db import connect

    code_text = (
        '1 — солдат (soldier)\n'
        '2 — перехватчик (interceptor)\n'
        '3 — БПЛА (drone)\n'
        '4 — БМП (bmp)\n'
        '5 — танк (tank)\n'
        '6 — вертолёт (helicopter)\n'
        '7 — самолёт (plane)\n'
        '8 — ракета (missile)\n'
        '9 — артиллерия (artillery)'
    )
    id_to_unit = {int(v['id']): k for k, v in UNITS.items()}

    async def give_unit(message, parts):
        if not await run.admin_ok(message.from_user.id):
            return await message.answer('⛔ Нет доступа.')
        if len(parts) != 3:
            return await message.answer('❌ Формат:\n/givepehot @username КОД КОЛИЧЕСТВО\n\nКоды:\n' + code_text)
        target = await app.find_user(parts[0])
        try:
            unit_id = int(parts[1]); amount = int(parts[2])
        except ValueError:
            return await message.answer('❌ Код и количество должны быть числами.')
        unit = id_to_unit.get(unit_id)
        if target is None:
            return await message.answer('❌ Пользователь не найден.')
        if unit is None:
            return await message.answer('❌ Неизвестный код техники.\n\n' + code_text)
        if amount <= 0 or amount > 1_000_000_000:
            return await message.answer('❌ Количество должно быть от 1 до 1 000 000 000.')
        db = await connect()
        try:
            await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?', (amount, target['user_id']))
            await db.commit()
        finally:
            await db.close()
        return await message.answer(f'✅ Выдано: {UNITS[unit]["title"]} × {amount} пользователю {parts[0]}.')

    old_text = run.text_handler
    @functools.wraps(old_text)
    async def final_text_handler(message, bot, *args, **kwargs):
        text = (message.text or '').strip(); parts = text.split()
        command = parts[0].split('@', 1)[0].lower() if parts else ''
        if command in ('/givepehot','givepehot','/giveunit','giveunit','/give'):
            return await give_unit(message, parts[1:])
        if text.lower() in ('коды','/коды','коды техники','/коды техники','/unitcodes'):
            if not await run.admin_ok(message.from_user.id):
                return await message.answer('⛔ Нет доступа.')
            return await message.answer('🎖 КОДЫ ТЕХНИКИ ДЛЯ ВЫДАЧИ\n\n' + code_text + '\n\nПример:\n/givepehot @macrasoft 1 100')
        return await old_text(message, bot, *args, **kwargs)
    run.text_handler = final_text_handler

    old_callback = run.callback
    @functools.wraps(old_callback)
    async def final_callback(c, tg_bot, *args, **kwargs):
        if c.data == 'a_give':
            return await app.safe(c, '🎖 ВЫДАТЬ ТЕХНИКУ\n\n/givepehot @username КОД КОЛИЧЕСТВО\n\nКоды:\n' + code_text, app.back('admin'))
        return await old_callback(c, tg_bot, *args, **kwargs)
    run.callback = final_callback
    run._wwd_admin_commands_final = True


def _run_with_finalize(main, *, debug=False):
    _finalize()
    return _ORIGINAL_ASYNCIO_RUN(main, debug=debug)

if not getattr(asyncio.run, '_wwd_final_bootstrap', False):
    _run_with_finalize._wwd_final_bootstrap = True
    asyncio.run = _run_with_finalize
