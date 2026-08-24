"""Final callback dispatcher for WorldWarDynasty.

Do not chain through app.callback: compatibility layers replace that attribute
and doing so can recurse forever. Route achievement/admin callbacks explicitly,
then call the installed hotfix callback object directly for everything else.
"""
import bot as app
import achievements
import hotfix_2026_08_24 as hotfix
from config import OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, UNITS
from db import connect, is_admin


def _is_admin(uid):
    return uid in OWNER_IDS or uid in (OWNER_ID, OWNER_ID2)


async def _admin_ok(uid):
    if _is_admin(uid):
        return True
    try:
        return bool(await is_admin(uid, ADMIN_ID))
    except Exception:
        return False


async def _admin_panel(c):
    if not await _admin_ok(c.from_user.id):
        return await c.answer('⛔ Нет доступа.', show_alert=True)
    return await app.safe(
        c,
        '⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел. Все действия доступны только владельцам/админам.',
        app.admin_kb(),
    )


async def _admin_section(c, data):
    if not await _admin_ok(c.from_user.id):
        return await c.answer('⛔ Нет доступа.', show_alert=True)
    fn = getattr(app, 'admin_section', None)
    if fn is None:
        return await c.answer('Раздел недоступен.', show_alert=True)
    return await fn(c, data)


async def _takeunit(m, parts):
    if not await _admin_ok(m.from_user.id):
        return await m.answer('⛔ Нет доступа.')
    if len(parts) != 3:
        return await m.answer('❌ Формат: /takeunit @username unit количество')
    target = await app.find_user(parts[0])
    unit = parts[1].lower()
    try:
        amount = int(parts[2])
    except ValueError:
        amount = 0
    if not target:
        return await m.answer('❌ Пользователь не найден.')
    if unit not in UNITS or amount <= 0:
        return await m.answer('❌ Неверная техника или количество.\nДоступно: ' + ', '.join(UNITS.keys()))
    db = await connect()
    try:
        cur = await db.execute(
            f'UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?',
            (amount, target['user_id']),
        )
        await db.commit()
    finally:
        await db.close()
    if cur.rowcount != 1:
        return await m.answer('❌ Не удалось изменить армию пользователя.')
    return await m.answer(f'✅ Списано: {amount} × {UNITS[unit]["title"]} у @{target["username"] or target["user_id"]}.')


def _real_callback():
    # This is the module-level function installed by hotfix_2026_08_24.
    # Calling it directly avoids the self-reference created by app.callback.
    return getattr(hotfix, 'callback', None) or getattr(app, '_original_callback', None)


async def _dispatch(c):
    data = c.data or ''
    if data == 'achievements':
        return await achievements.menu(c)
    if data.startswith('ach:'):
        return await achievements.detail(c, data.split(':', 1)[1])
    if data.startswith('ach_claim:'):
        return await achievements.claim(c, data.split(':', 1)[1])
    if data == 'admin':
        return await _admin_panel(c)
    if data.startswith('a_'):
        return await _admin_section(c, data)

    fn = _real_callback()
    if fn is None:
        return await c.answer('Callback handler недоступен.', show_alert=True)
    return await fn(c, c.bot)


def install():
    # Exactly one final wrapper; it never invokes app.callback.
    app.callback = _dispatch
    previous_text = getattr(app, 'text_handler', None)

    async def text_handler(m, bot):
        text = (m.text or '').strip()
        parts = text.split()
        low = text.lower()
        if low in ('адм', 'админ', '/адм', '/админ', '/admin', '/adm'):
            if await _admin_ok(m.from_user.id):
                return await m.answer(
                    '⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел.',
                    reply_markup=app.admin_kb(),
                )
            return await m.answer('⛔ Нет доступа.')
        if parts and parts[0].split('@')[0].lower() == '/takeunit':
            return await _takeunit(m, parts[1:])
        if previous_text is not None:
            return await previous_text(m, bot)

    app.text_handler = text_handler
