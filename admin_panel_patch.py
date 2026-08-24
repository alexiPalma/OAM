import bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import connect, set_setting
from settings import get_int, get_str


def _kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t,d in row] for row in rows])


def _back(target='admin'):
    return _kb([[('⬅️ Назад', target)]])


async def admin_section(c, s):
    if not await bot.admin(c.from_user.id):
        return await c.answer('Нет доступа.', show_alert=True)

    if s == 'a_currency':
        return await bot.safe(c, '💰 ВАЛЮТА\n\n/givecash @user сумма — выдать валюту\n\nКурс и значения можно менять через настройки администратора.', _back())

    if s == 'a_bonus':
        return await bot.safe(c, '🎁 БОНУСЫ\n\nЕжедневный бонус настроен в игре.\n\n/setbonus daily 500000 — изменить базовое значение\n\n📌 Подписка на канал НЕ является частью ежедневного бонуса. Она находится в разделе «Заработать».', _back())

    if s == 'a_cases':
        return await bot.safe(c, '📦 КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n10% — 10 солдат\n15% — 11 перехватчиков\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета', _back())

    if s == 'a_promos':
        return await bot.safe(c, '🎟 ПРОМОКОДЫ\n\nИспользуйте /promo для ввода промокода.\n\nУправление промокодами подключается через отдельные команды администратора.', _back())

    if s == 'a_earn':
        return await bot.safe(c, '📢 ЗАРАБОТАТЬ\n\nДобавление заданий:\n\n🚀 /addboost https://t.me/... 150000\n📢 /addchannel https://t.me/... 150000\n👥 /addgroup https://t.me/... 150000\n\nЭти задания появляются пользователям именно в «Заработать».', _kb([[('🚀 Буст канала','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Подписка на группу','earn_add:group')],[('⬅️ Назад','admin')]]))

    if s == 'a_donate':
        return await bot.donate(c)

    if s == 'a_rules':
        return await bot.safe(c, '📕 ПРАВИЛА\n\nТекущий текст можно изменить командой:\n/setrule новый текст', _back())

    if s == 'a_admins':
        db = await connect(); cur = await db.execute('SELECT user_id FROM admins ORDER BY user_id'); rows = await cur.fetchall(); await db.close()
        ids = '\n'.join(f'• {r["user_id"]}' for r in rows) or '• Администраторов нет'
        return await bot.safe(c, f'👥 АДМИНИСТРАТОРЫ\n\n{ids}\n\nOWNER_ID: {bot.ADMIN_ID}', _back())

    if s == 'a_give':
        return await bot.safe(c, '🎖 ВЫДАТЬ / СПИСАТЬ\n\n💰 Валюта:\n/givecash @user 100000\n\n🎖 Армия:\n/givepehot @user 1 100\n\nНомера:\n1 — пехота\n2 — перехватчик\n3 — БПЛА\n4 — БМП\n5 — танк\n6 — вертолёт\n7 — самолёт\n8 — ракета\n9 — артиллерия', _back())

    if s == 'a_broadcast':
        return await bot.safe(c, '📣 РАССЫЛКА\n\nОтправка сообщения всем пользователям:\n/broadcast текст', _back())

    if s == 'a_stats':
        from db import users_count
        return await bot.safe(c, f'📊 СТАТИСТИКА\n\n👥 Игроков: {await users_count()}', _back())

    if s == 'a_edit':
        return await bot.safe(c, '✏️ РЕДАКТИРОВАТЬ СООБЩЕНИЯ\n\nИзменить помощь:\n/setmsg help новый текст\n\nИзменить правила:\n/setmsg rules новый текст\n\nТекст сохраняется в настройках и используется ботом.', _back())

    if s == 'a_farms':
        return await bot.safe(c, '🏭 ФЕРМЫ\n\nУровень: 1–10\nВыплата: раз в час\nНалог: накапливается после выплаты\nМаксимальный налог: $1 000 000\n\nПараметры фермы находятся в config.py.', _back())

    if s == 'a_battles':
        return await bot.safe(c, '⚔️ БОИ\n\n⏱ КД атаки: 10 минут\n⏱ Боевой таймер: 15 секунд\n📉 Проигравший: −20% армии\n💰 Победитель: 5% стоимости уничтоженного\n💰 Проигравший: 2% стоимости своих потерь', _back())

    return await bot.safe(c, '⚙️ Раздел не найден.', _back())


bot.admin_section = admin_section
