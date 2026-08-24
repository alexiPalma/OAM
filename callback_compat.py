"""Final aiogram callback dispatcher.

The important rule here is: never call app.callback from inside the final
callback. run.py freezes the runtime callback before wrappers are installed,
so this dispatcher always has a stable non-recursive target.
"""
import bot as app
import achievements
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
    return await app.safe(c, '⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел.', app.admin_kb())


async def _admin_section(c, data):
    if not await _admin_ok(c.from_user.id):
        return await c.answer('⛔ Нет доступа.', show_alert=True)
    # admin_section is installed by the runtime layer. If a project version
    # does not expose it, fall back to the stable runtime callback instead of
    # displaying a fake "section opened" message.
    fn = getattr(app, 'admin_section', None)
    if fn is not None:
        return await fn(c, data)
    runtime = getattr(app, '_runtime_callback', None)
    if runtime is not None:
        return await runtime(c, c.bot)
    return await c.answer('Раздел недоступен.', show_alert=True)


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
        cur = await db.execute(f'UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?', (amount, target['user_id']))
        await db.commit()
    finally:
        await db.close()
    if cur.rowcount != 1:
        return await m.answer('❌ Не удалось изменить армию пользователя.')
    return await m.answer(f'✅ Списано: {amount} × {UNITS[unit]["title"]} у @{target["username"] or target["user_id"]}.')


async def _takeunit_menu(c):
    if not await _admin_ok(c.from_user.id):
        return await c.answer('⛔ Нет доступа.', show_alert=True)
    text = (
        '➖ Списать технику\n\n'
        'Команда:\n'
        '/takeunit @username тип количество\n\n'
        'Типы:\n' + ', '.join(UNITS.keys()) +
        '\n\nПример:\n/takeunit @player soldier 100'
    )
    return await app.safe(c, text, app.back('admin'))


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
    if data == 'a_takeunit':
        return await _takeunit_menu(c)
    if data.startswith('a_'):
        return await _admin_section(c, data)

    # Every ordinary callback is sent to the frozen runtime handler. It is
    # the handler that existed before this final wrapper, so 'home' and all
    # other back buttons cannot recurse into this function.
    runtime = getattr(app, '_runtime_callback', None)
    if runtime is None:
        return await c.answer('Callback handler недоступен.', show_alert=True)
    return await runtime(c, c.bot)


def install():
    app.callback = _dispatch
    previous_text = getattr(app, 'text_handler', None)

    async def text_handler(m, bot):
        text = (m.text or '').strip()
        parts = text.split()
        low = text.lower()
        if low in ('адм', 'админ', '/адм', '/админ', '/admin', '/adm'):
            if await _admin_ok(m.from_user.id):
                return await m.answer('⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел.', reply_markup=app.admin_kb())
            return await m.answer('⛔ Нет доступа.')
        if parts and parts[0].split('@')[0].lower() == '/takeunit':
            return await _takeunit(m, parts[1:])
        if previous_text is not None:
            return await previous_text(m, bot)

    app.text_handler = text_handler
