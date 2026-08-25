"""Stable launcher for WorldWarDynasty.

The fix layer lives in config.py. The old launcher executes run.py as
__main__, which means the import hook in config.py never gets a chance to
patch the already-running launcher. This file imports run as a module first,
activates the fix layer explicitly, adds the admin unit-code commands, and
then starts the patched dispatcher.
"""
import asyncio

import run
from config import _patch_run, OWNER_IDS
from db import connect, is_admin


UNIT_CODES = {
    1: ('soldier', '🪖 Пехота'),
    2: ('interceptor', '🎯 Дрон-перехватчик'),
    3: ('drone', '🛩 БПЛА'),
    4: ('bmp', '🚙 БМП'),
    5: ('tank', '🛡 Танк'),
    6: ('helicopter', '🚁 Вертолёт'),
    7: ('plane', '✈️ Самолёт'),
    8: ('missile', '🚀 Ракета'),
    9: ('artillery', '💥 Артиллерия'),
}


def unit_codes_text():
    lines = ['🎖 КОДЫ ТЕХНИКИ ДЛЯ АДМИНА', '']
    for code, (_key, title) in UNIT_CODES.items():
        lines.append(f'{code} — {title}')
    lines += [
        '',
        '📌 Выдача:',
        '/givepehot @username КОД КОЛИЧЕСТВО',
        '',
        'Пример:',
        '/givepehot @macrasoft 1 100',
        '→ 100 пехотинцев',
        '',
        'Также:',
        '/givecash @username СУММА',
    ]
    return '\n'.join(lines)


async def admin_access(uid):
    if uid in OWNER_IDS:
        return True
    try:
        return bool(await is_admin(uid, run.ADMIN_ID))
    except Exception:
        return False


async def fixed_give(message, parts):
    if not await admin_access(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')
    if len(parts) != 3:
        return await message.answer(
            '❌ Формат:\n/givepehot @username КОД КОЛИЧЕСТВО\n\n' + unit_codes_text()
        )

    target_name, code_s, amount_s = parts
    try:
        code = int(code_s)
        amount = int(amount_s)
    except ValueError:
        return await message.answer('❌ Код и количество должны быть числами.')
    if code not in UNIT_CODES or amount <= 0:
        return await message.answer('❌ Неверный код или количество.\n\n' + unit_codes_text())

    target = await run.app.find_user(target_name)
    if not target:
        return await message.answer('❌ Пользователь не найден.')

    unit, title = UNIT_CODES[code]
    db = await connect()
    try:
        await db.execute(
            f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',
            (amount, target['user_id']),
        )
        await db.commit()
    finally:
        await db.close()

    return await message.answer(
        f'✅ Выдано.\n\n{title} × {amount}\n👤 {target_name}\n🔢 Код: {code}'
    )


async def fixed_givecash(message, parts):
    if not await admin_access(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')
    if len(parts) != 2:
        return await message.answer('❌ Формат: /givecash @username сумма')
    target = await run.app.find_user(parts[0])
    try:
        amount = int(parts[1])
    except ValueError:
        amount = 0
    if not target or amount <= 0:
        return await message.answer('❌ Неверные данные.')
    db = await connect()
    try:
        await db.execute(
            'UPDATE users SET balance=balance+? WHERE user_id=?',
            (amount, target['user_id']),
        )
        await db.commit()
    finally:
        await db.close()
    return await message.answer(f'✅ Выдано ${run.app.money(amount)} пользователю {parts[0]}.')


async def codes(message):
    if not await admin_access(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')
    return await message.answer(unit_codes_text())


# Import run as a module first, then activate config.py's complete runtime fix layer.
_patch_run(run)
_ORIGINAL_TEXT_HANDLER = run.text_handler


async def patched_text_handler(message, bot, *args, **kwargs):
    text = (message.text or '').strip()
    parts = text.split()
    command = parts[0].split('@')[0].lower() if parts else ''
    if command == '/givepehot':
        return await fixed_give(message, parts[1:])
    if command == '/givecash':
        return await fixed_givecash(message, parts[1:])
    if command in ('/коды', '/codes', 'коды'):
        return await codes(message)
    return await _ORIGINAL_TEXT_HANDLER(message, bot, *args, **kwargs)


run.text_handler = patched_text_handler


if __name__ == '__main__':
    asyncio.run(run.main())
