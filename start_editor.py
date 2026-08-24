import bot
from db import setting

async def start(m):
    await bot.ensure_user(m.from_user.id, m.from_user.username)
    u = await bot.user(m.from_user.id)
    value = await setting('msg_start')
    if value is None:
        value = '⚔️ WorldWarDynasty\n\n💵 Баланс: ${balance}\n🏭 Ферма: {farm}/10\n\n🛰 Центр управления войсками:'
    try:
        text = value.format(balance=bot.money(u['balance']), farm=u['farm_level'])
    except Exception:
        text = value
    await m.answer(text, reply_markup=bot.home_kb(await bot.admin(m.from_user.id)))

bot.start = start
