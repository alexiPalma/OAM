"""Stable entry point for WorldWarDynasty.

Do not install the old runtime/hotfix wrapper chain here. Those wrappers
replaced each other's handlers and caused the RecursionError in callbacks and
text handling. The base bot owns normal routing; this file adds only isolated
compatibility handlers for achievements and admin deductions.
"""
import asyncio

import bot as app
import achievements
from config import OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, UNITS
from db import connect, is_admin


async def admin_ok(uid: int) -> bool:
    if uid in OWNER_IDS or uid in (OWNER_ID, OWNER_ID2):
        return True
    try:
        return bool(await is_admin(uid, ADMIN_ID))
    except Exception:
        return False


async def take_unit(message, parts):
    if not await admin_ok(message.from_user.id):
        return await message.answer("⛔ Нет доступа.")
    if len(parts) != 3:
        return await message.answer("❌ Формат: /takeunit @username тип количество\nПример: /takeunit @player soldier 100")
    target = await app.find_user(parts[0])
    unit = parts[1].lower()
    try:
        amount = int(parts[2])
    except ValueError:
        amount = 0
    if target is None:
        return await message.answer("❌ Пользователь не найден.")
    if unit not in UNITS or amount <= 0:
        return await message.answer("❌ Неверная техника или количество.\nДоступно: " + ", ".join(UNITS.keys()))
    db = await connect()
    try:
        cur = await db.execute(f"UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?", (amount, target["user_id"]))
        await db.commit()
    finally:
        await db.close()
    if cur.rowcount != 1:
        return await message.answer("❌ Не удалось изменить армию пользователя.")
    name = "@" + target["username"] if target["username"] else str(target["user_id"])
    return await message.answer(f"✅ Списано: {amount} × {UNITS[unit]['title']} у {name}.")


async def take_cash(message, parts):
    if not await admin_ok(message.from_user.id):
        return await message.answer("⛔ Нет доступа.")
    if len(parts) != 2:
        return await message.answer("❌ Формат: /takecash @username сумма\nПример: /takecash @player 100000")
    target = await app.find_user(parts[0])
    try:
        amount = int(parts[1])
    except ValueError:
        amount = 0
    if target is None:
        return await message.answer("❌ Пользователь не найден.")
    if amount <= 0:
        return await message.answer("❌ Сумма должна быть больше нуля.")
    db = await connect()
    try:
        cur = await db.execute("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?", (amount, target["user_id"]))
        await db.commit()
    finally:
        await db.close()
    if cur.rowcount != 1:
        return await message.answer("❌ Не удалось изменить баланс пользователя.")
    name = "@" + target["username"] if target["username"] else str(target["user_id"])
    return await message.answer(f"✅ Списано ${app.money(amount)} у {name}.")


async def take_menu(c):
    if not await admin_ok(c.from_user.id):
        return await c.answer("⛔ Нет доступа.", show_alert=True)
    text = (
        "➖ ВЫДАТЬ / СПИСАТЬ\n\n"
        "💵 Деньги:\n"
        "/givecash @username сумма\n"
        "/takecash @username сумма\n\n"
        "🎖 Техника:\n"
        "/givepehot @username ID количество\n"
        "/takeunit @username тип количество\n\n"
        "Типы техники:\n" + ", ".join(UNITS.keys())
    )
    return await app.safe(c, text, app.back("admin"))


# Capture the original handlers once, before replacing them.
ORIGINAL_CALLBACK = app.callback
ORIGINAL_TEXT = app.text_handler


async def callback(c, tg_bot):
    data = c.data or ""
    if data == "achievements":
        return await achievements.menu(c)
    if data.startswith("ach:"):
        return await achievements.detail(c, data.split(":", 1)[1])
    if data.startswith("ach_claim:"):
        return await achievements.claim(c, data.split(":", 1)[1])
    if data in ("a_give", "a_takeunit"):
        return await take_menu(c)
    return await ORIGINAL_CALLBACK(c, tg_bot)


async def text_handler(message, tg_bot):
    text = (message.text or "").strip()
    low = text.lower()
    parts = text.split()
    command = parts[0].split("@")[0].lower() if parts else ""
    if low in ("адм", "админ", "/адм", "/админ", "/admin", "/adm"):
        if not await admin_ok(message.from_user.id):
            return await message.answer("⛔ Нет доступа.")
        return await message.answer("⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел:", reply_markup=app.admin_kb())
    if command == "/takeunit":
        return await take_unit(message, parts[1:])
    if command == "/takecash":
        return await take_cash(message, parts[1:])
    return await ORIGINAL_TEXT(message, tg_bot)


async def main():
    await achievements.init_achievements()
    achievements.install_sync()
    app.callback = callback
    app.text_handler = text_handler
    await app.main()


if __name__ == "__main__":
    asyncio.run(main())
