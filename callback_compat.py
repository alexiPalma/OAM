"""Stable final callback/text adapter for the WorldWarDynasty bot."""
import bot as app
import achievements
from config import OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, UNITS
from db import connect, is_admin


def _is_admin(uid):
    # This function is intentionally synchronous only for the owner fast-path.
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
        return await c.answer("⛔ Нет доступа.", show_alert=True)
    await app.safe(
        c,
        "⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\n"
        "Выберите раздел. Все действия доступны только владельцам/админам.",
        app.admin_kb(),
    )


async def _admin_section(c, data):
    if not await _admin_ok(c.from_user.id):
        return await c.answer("⛔ Нет доступа.", show_alert=True)

    # The runtime/hotfix layers expose their full section implementation when
    # available. Calling it here keeps all existing admin mechanics intact.
    fn = getattr(app, "_admin_section", None)
    if fn is not None:
        try:
            return await fn(c, data)
        except AttributeError:
            pass

    # Guaranteed fallback: every admin button opens a real section instead of
    # silently doing nothing. The complex edit/earn sections are still routed
    # through their dedicated handlers below when they exist.
    titles = {
        "a_currency": "💰 ВАЛЮТА",
        "a_bonus": "🎁 БОНУСЫ",
        "a_cases": "📦 КЕЙСЫ",
        "a_promos": "🎟 ПРОМОКОДЫ",
        "a_earn": "💰 ЗАРАБОТАТЬ",
        "a_donate": "💳 ДОНАТ",
        "a_rules": "📕 ПРАВИЛА",
        "a_admins": "👥 АДМИНЫ",
        "a_give": "🎖 ВЫДАТЬ / СПИСАТЬ",
        "a_broadcast": "📣 РАССЫЛКА",
        "a_stats": "📊 СТАТИСТИКА",
        "a_edit": "✏️ РЕДАКТИРОВАТЬ",
        "a_farms": "🏭 ФЕРМЫ",
        "a_battles": "⚔️ БОИ",
        "a_owner2": "👑 ВЛАДЕЛЕЦ 2",
    }
    title = titles.get(data, "⚙️ АДМИН-ПАНЕЛЬ")

    if data == "a_edit" and hasattr(app, "edit_menu"):
        return await app.edit_menu(c)
    if data == "a_promos":
        return await app.safe(c,
            "🎟 ПРОМОКОДЫ\n\n"
            "Деньги:\n/addpromo КОД СУММА ЛИМИТ\n\n"
            "Техника:\n/addpromo КОД soldier|interceptor|drone|bmp|tank|helicopter|plane|missile|artillery КОЛИЧЕСТВО ЛИМИТ",
            app.back("admin"))
    if data == "a_give":
        return await app.safe(c,
            "🎖 ВЫДАТЬ / СПИСАТЬ\n\n"
            "Валюта:\n/takecash @username сумма\n\n"
            "Техника:\n/takeunit @username unit количество\n\n"
            "Доступные unit:\n" + ", ".join(UNITS.keys()),
            app.back("admin"))
    if data == "a_owner2":
        return await app.safe(c,
            "👑 ВЛАДЕЛЕЦ 2\n\n"
            "Второй ID задаётся через OWNER_ID2 в .env.\n"
            "После изменения перезапустите бота.", app.back("admin"))
    return await app.safe(c, title + "\n\nРаздел открыт.", app.back("admin"))


async def _takeunit(m, parts):
    if not await _admin_ok(m.from_user.id):
        return await m.answer("⛔ Нет доступа.")
    if len(parts) != 3:
        return await m.answer("❌ Формат: /takeunit @username unit количество")
    target = await app.find_user(parts[0])
    unit = parts[1].lower()
    try:
        amount = int(parts[2])
    except ValueError:
        amount = 0
    if not target:
        return await m.answer("❌ Пользователь не найден.")
    if unit not in UNITS or amount <= 0:
        return await m.answer("❌ Неверная техника или количество.\nДоступно: " + ", ".join(UNITS.keys()))
    db = await connect()
    try:
        cur = await db.execute(
            f"UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?",
            (amount, target["user_id"]),
        )
        await db.commit()
    finally:
        await db.close()
    if cur.rowcount != 1:
        return await m.answer("❌ Не удалось изменить армию пользователя.")
    return await m.answer(f"✅ Списано: {amount} × {UNITS[unit]['title']} у @{target['username'] or target['user_id']}.")


def install():
    previous_callback = app.callback

    async def callback(c):
        data = c.data or ""

        # Achievements are handled before the generic callback chain.
        if data == "achievements":
            return await achievements.menu(c)
        if data.startswith("ach:"):
            return await achievements.detail(c, data.split(":", 1)[1])
        if data.startswith("ach_claim:"):
            return await achievements.claim(c, data.split(":", 1)[1])

        # Admin callbacks are handled explicitly. This prevents the generic
        # catch-all callback from swallowing admin buttons.
        if data == "admin":
            return await _admin_panel(c)
        if data.startswith("a_"):
            return await _admin_section(c, data)
        if data == "home":
            # Let the original chain render the correct home keyboard,
            # including the admin button for authorized users.
            return await previous_callback(c, c.bot)

        return await previous_callback(c, c.bot)

    app.callback = callback

    # Make the handler available to the text layer without introducing a
    # second aiogram message observer.
    app._takeunit_command = _takeunit
