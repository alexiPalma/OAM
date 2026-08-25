"""WorldWarDynasty final runtime bootstrap.

run.py is executed as __main__. The old patcher was installed as an import
hook and therefore did not patch __main__. This bootstrap activates the same
real fixes immediately before the bot's event loop starts.
"""
import asyncio
import functools
import sys

_ORIGINAL_ASYNCIO_RUN = asyncio.run


def _finalize():
    try:
        import config
        import bot as app
        main = sys.modules.get('__main__')
        if main is None or not str(getattr(main, '__file__', '')).endswith('run.py'):
            return

        # config._patch_run expects a `case` symbol in run.py, but the real
        # implementation lives in bot.py. Supplying that alias makes the
        # existing patcher execute instead of silently returning False.
        if not hasattr(main, 'case') and hasattr(app, 'case'):
            main.case = app.case

        patcher = getattr(config, '_patch_run', None)
        if patcher:
            patcher(main)

        _install_admin_commands(main)
        _install_group_guard()
        _install_achievement_guard()
    except Exception as exc:
        print(f'[WorldWarDynasty] final bootstrap warning: {exc}')


def _install_achievement_guard():
    try:
        import achievements
        achievements.REQ_KEYS = (
            'kill_soldier', 'kill_drone', 'kill_tank', 'kill_bmp',
            'kill_helicopter', 'kill_plane', 'kill_missile', 'kill_interceptor',
        )
        achievements.REQ_NAMES = (
            '💀 Уничтожено солдат', '💀 Уничтожено БПЛА',
            '💀 Уничтожено танков', '💀 Уничтожено БМП',
            '💀 Уничтожено вертолётов', '💀 Уничтожено самолётов',
            '💀 Уничтожено ракет', '💀 Уничтожено перехватчиков',
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
            return await message.answer(
                '❌ Формат:\n/givepehot @username КОД КОЛИЧЕСТВО\n\n'
                f'Коды техники:\n{code_text}'
            )
        target = await app.find_user(parts[0])
        try:
            unit_id = int(parts[1])
            amount = int(parts[2])
        except ValueError:
            return await message.answer('❌ Код и количество должны быть числами.')
        unit = id_to_unit.get(unit_id)
        if target is None:
            return await message.answer('❌ Пользователь не найден.')
        if unit is None:
            return await message.answer(f'❌ Неизвестный код техники.\n\n{code_text}')
        if amount <= 0 or amount > 1_000_000_000:
            return await message.answer('❌ Количество должно быть от 1 до 1 000 000 000.')
        db = await connect()
        try:
            await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?', (amount, target['user_id']))
            await db.commit()
        finally:
            await db.close()
        return await message.answer(
            f'✅ Выдано.\n\n👤 {parts[0]}\n🎖 {UNITS[unit]["title"]}\n'
            f'🔢 Количество: {amount}\n🆔 Код: {unit_id}'
        )

    old_text = run.text_handler

    @functools.wraps(old_text)
    async def final_text_handler(message, bot, *args, **kwargs):
        text = (message.text or '').strip()
        parts = text.split()
        command = parts[0].split('@', 1)[0].lower() if parts else ''
        low = text.lower()
        if command in ('/givepehot', 'givepehot', '/giveunit', 'giveunit', '/give'):
            return await give_unit(message, parts[1:])
        if low in ('коды', '/коды', 'коды техники', '/коды техники', '/unitcodes'):
            if not await run.admin_ok(message.from_user.id):
                return await message.answer('⛔ Нет доступа.')
            return await message.answer(
                '🎖 КОДЫ ТЕХНИКИ ДЛЯ ВЫДАЧИ\n\n' + code_text +
                '\n\nПример:\n/givepehot @macrasoft 1 100'
            )
        return await old_text(message, bot, *args, **kwargs)

    run.text_handler = final_text_handler

    old_callback = run.callback

    @functools.wraps(old_callback)
    async def final_callback(c, tg_bot, *args, **kwargs):
        if c.data == 'a_give':
            return await app.safe(
                c,
                '🎖 ВЫДАТЬ ТЕХНИКУ\n\n'
                '/givepehot @username КОД КОЛИЧЕСТВО\n\n'
                f'Коды:\n{code_text}\n\n'
                'Пример:\n/givepehot @macrasoft 1 100',
                app.back('admin'),
            )
        if c.data == 'a_promos':
            return await app.safe(
                c,
                '🎟 ПРОМОКОДЫ\n\n'
                '/addpromo КОД СУММА ЛИМИТ\n'
                '/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n'
                '/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\n'
                'Техника: soldier, interceptor, drone, bmp, artillery, tank, helicopter, plane, missile\n'
                'Кейсы: case1, case2, donate_case',
                app.back('admin'),
            )
        return await old_callback(c, tg_bot, *args, **kwargs)

    run.callback = final_callback
    run._wwd_admin_commands_final = True


def _install_group_guard():
    try:
        from aiogram.dispatcher.dispatcher import Dispatcher
    except Exception:
        return
    if getattr(Dispatcher, '_wwd_group_guard_final', False):
        return

    old_feed = Dispatcher.feed_update

    async def feed_update(self, bot, update, **kwargs):
        event = getattr(update, 'callback_query', None)
        if event is not None and getattr(event, 'message', None) is not None:
            if event.message.chat.type in ('group', 'supergroup'):
                data = str(event.data or '')
                marker = '|wwdu:'
                if marker in data:
                    _, raw_owner = data.rsplit(marker, 1)
                    try:
                        owner = int(raw_owner)
                    except ValueError:
                        owner = -1
                    if owner != event.from_user.id:
                        try:
                            await event.answer('⛔ Это меню принадлежит другому пользователю.', show_alert=True)
                        except Exception:
                            pass
                        return None
        return await old_feed(self, bot, update, **kwargs)

    Dispatcher.feed_update = feed_update
    Dispatcher._wwd_group_guard_final = True


def _run_with_finalize(main, *, debug=False):
    _finalize()
    return _ORIGINAL_ASYNCIO_RUN(main, debug=debug)


if not getattr(asyncio.run, '_wwd_final_bootstrap', False):
    _run_with_finalize._wwd_final_bootstrap = True
    asyncio.run = _run_with_finalize
