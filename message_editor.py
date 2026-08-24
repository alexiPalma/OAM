import bot
from db import set_setting, setting

TEMPLATES = {
    'start': ('🏠 Главное меню', '⚔️ WorldWarDynasty\n\n💵 Баланс: ${balance}\n🏭 Ферма: {farm}/10\n\n🛰 Центр управления войсками:'),
    'profile': ('👤 Профиль', '👤 WorldWarDynasty • ПРОФИЛЬ\n\n👤 Юзер: {name}\n💵 Баланс: ${balance}\n🏭 Ферма: {farm}/10\n🏆 Побед: {wins}\n💀 Поражений: {losses}\n⚔️ КД атаки: {cd}\n\n🎯 УНИЧТОЖЕНО\n{kills}'),
    'army': ('🎖 Армия', '🎖 WorldWarDynasty • АРМИЯ\n\n{army}'),
    'shop': ('🛒 Военный арсенал', '🛒 WorldWarDynasty • ВОЕННЫЙ АРСЕНАЛ\n\nВыберите единицу. Затем бот спросит количество.'),
    'farm': ('🏭 Ферма', '🏭 WorldWarDynasty • ФЕРМА\n\nУровень: {level}/10\nПроизводство: ${income}/час\nНалог: ${tax}\nСтатус: {status}'),
    'bonus': ('🎁 Ежедневный бонус', '🎁 WorldWarDynasty • ЕЖЕДНЕВНЫЙ БОНУС\n\n{prizes}'),
    'cases': ('📦 Кейсы', '📦 WorldWarDynasty • КЕЙСЫ\n\n{cases}'),
    'donate': ('💳 Донат', '💳 WorldWarDynasty • ДОНАТ\n\n50 ⭐ — ${d50}\n100 ⭐ — ${d100}\n500 ⭐ — ${d500}\n\n📨 {contact}'),
    'top': ('🏆 Топ вояк', '🏆 WorldWarDynasty • ТОП ВОЯК\n\n{top}'),
    'earn': ('💰 Заработать', '💰 ЗАРАБОТАТЬ\n\n{tasks}'),
    'attack': ('⚔️ Атака', '⚔️ WorldWarDynasty • ПРОТИВНИКИ\n\n{players}'),
    'opponent': ('🎯 Противник', '🎯 WorldWarDynasty • ПРОТИВНИК\n\n👤 {name}\n\n{army}'),
    'battle_start': ('⚔️ Бой', '⚔️ БОЙ НАЧАЛСЯ\n\n{phrase}'),
    'battle_result_win': ('🏆 Победа', '🏆 WIN\n\n💰 Победитель получил: ${reward}\n📉 Армия проигравшего: −20%\n💵 Проигравшему: +${loser_reward}\n\n{report}'),
    'battle_result_loss': ('💀 Поражение', '💀 LOSS\n\n📉 Твоя армия: −20%\n💵 Компенсация: ${reward}\n\n{report}'),
    'help': ('ℹ️ Помощь', 'ℹ️ WorldWarDynasty • ПОМОЩЬ\n\n{help}'),
    'rules': ('📕 Правила', '📕 WorldWarDynasty • ПРАВИЛА\n\n{rules}'),
    'admin_currency': ('💰 Валюта', '💰 ВАЛЮТА\n\n/givecash @user сумма\n\nКурс и значения можно менять через настройки администратора.'),
    'admin_bonus': ('🎁 Бонусы', '🎁 БОНУСЫ\n\nЕжедневный бонус: ${daily}\n\nПодписка на канал не является частью ежедневного бонуса.'),
    'admin_cases': ('📦 Кейсы', '📦 КЕЙСЫ\n\n{cases}'),
    'admin_promos': ('🎟 Промокоды', '🎟 ПРОМОКОДЫ\n\nИспользуйте /promo для ввода промокода.'),
    'admin_earn': ('💰 Заработать', '📢 ЗАРАБОТАТЬ\n\n🚀 /addboost https://t.me/... 150000\n📢 /addchannel https://t.me/... 150000\n👥 /addgroup https://t.me/... 150000'),
    'admin_donate': ('💳 Донат', '💳 ДОНАТ\n\n50 ⭐ — ${d50}\n100 ⭐ — ${d100}\n500 ⭐ — ${d500}\n\n📨 {contact}'),
    'admin_rules': ('📕 Правила', '📕 ПРАВИЛА\n\n/setrule новый текст'),
    'admin_admins': ('👥 Админы', '👥 АДМИНИСТРАТОРЫ\n\n{admins}'),
    'admin_give': ('🎖 Выдать / списать', '🎖 ВЫДАТЬ / СПИСАТЬ\n\n/givecash @user 100000\n/givepehot @user 1 100'),
    'admin_broadcast': ('📣 Рассылка', '📣 РАССЫЛКА\n\n/broadcast текст'),
    'admin_stats': ('📊 Статистика', '📊 СТАТИСТИКА\n\n👥 Игроков: {count}'),
    'admin_edit': ('✏️ Редактировать', '✏️ РЕДАКТИРОВАТЬ\n\nВыберите сообщение, которое хотите изменить.'),
    'admin_farms': ('🏭 Фермы', '🏭 ФЕРМЫ\n\nУровни: 1–10\nВыплата: раз в час\nМаксимальный налог: $1 000 000'),
    'admin_battles': ('⚔️ Бои', '⚔️ БОИ\n\nКД атаки: 10 минут\nБоевой таймер: 15 секунд\nПроигравший: −20% армии'),
}


def _key_for(text):
    s=str(text or '')
    checks=[('ПРОФИЛЬ','profile'),('АРМИЯ','army'),('ВОЕННЫЙ АРСЕНАЛ','shop'),('ФЕРМА','farm'),('ЕЖЕДНЕВНЫЙ БОНУС','bonus'),('КЕЙСЫ','cases'),('ДОНАТ','donate'),('ТОП ВОЯК','top'),('ПРОТИВНИКИ','attack'),('ПРОТИВНИК','opponent'),('БОЙ НАЧАЛСЯ','battle_start'),('🏆 WIN','battle_result_win'),('💀 LOSS','battle_result_loss'),('ПОМОЩЬ','help'),('ПРАВИЛА','rules'),('ВАЛЮТА','admin_currency'),('БОНУСЫ','admin_bonus'),('ПРОМОКОДЫ','admin_promos'),('ЗАРАБОТАТЬ','admin_earn'),('АДМИНИСТРАТОРЫ','admin_admins'),('ВЫДАТЬ / СПИСАТЬ','admin_give'),('РАССЫЛКА','admin_broadcast'),('СТАТИСТИКА','admin_stats'),('РЕДАКТИРОВАТЬ','admin_edit'),('БОИ','admin_battles')]
    for marker,key in checks:
        if marker in s:return key
    return None

_orig_safe=bot.safe
async def safe(c,text,markup=None):
    key=_key_for(text)
    if key:
        value=await setting('msg_'+key)
        if value is not None:
            u=await bot.user(c.from_user.id)
            ctx={'balance':bot.money(u['balance']) if u else '0','farm':u['farm_level'] if u else 1,'wins':u['attacks_won'] if u else 0,'losses':u['attacks_lost'] if u else 0,'cd':bot.cd_text(u) if u else 'ГОТОВО','name':('@'+u['username']) if u and u['username'] else 'не указан'}
            try:text=str(value).format(**ctx)
            except Exception:text=str(value)
    return await _orig_safe(c,text,markup)
bot.safe=safe

async def admin_section(c,s):
    if not await bot.admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    if s=='a_edit':
        from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
        rows=[[InlineKeyboardButton(text=title,callback_data='a_editmsg:'+key)] for key,(title,_) in TEMPLATES.items()]
        rows.append([InlineKeyboardButton(text='⬅️ Назад',callback_data='admin')])
        return await bot.safe(c,'✏️ РЕДАКТИРОВАТЬ — АБСОЛЮТНО ВСЕ СООБЩЕНИЯ\n\nВыберите любой экран. Здесь собраны тексты пользователя и всех разделов админ-панели.',InlineKeyboardMarkup(inline_keyboard=rows))
    if s.startswith('a_editmsg:'):
        key=s.split(':',1)[1]
        if key not in TEMPLATES:return await c.answer('Сообщение не найдено.',show_alert=True)
        title,default=TEMPLATES[key];current=await setting('msg_'+key) or default
        bot.STATE[c.from_user.id]=('editmsg',key)
        return await bot.safe(c,f'✏️ {title}\n\nТЕКУЩИЙ ТЕКСТ:\n\n{current}\n\nОтправьте одним сообщением новый полный текст. Доступные переменные: {{balance}}, {{farm}}, {{name}}, {{wins}}, {{losses}}, {{cd}}.',InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬅️ Назад',callback_data='a_edit')]]))
    return await bot._original_admin_section(c,s)

bot._original_admin_section=getattr(bot,'admin_section',lambda c,s:bot.safe(c,'Раздел не найден.'))
bot.admin_section=admin_section

_orig_text=bot.text_handler
async def text_handler(m,bot_instance):
    st=bot.STATE.get(m.from_user.id)
    if st and st[0]=='editmsg' and await bot.admin(m.from_user.id):
        key=st[1]
        if key in TEMPLATES:
            await set_setting('msg_'+key,m.text or '')
            bot.STATE.pop(m.from_user.id,None)
            return await m.answer('✅ Текст сохранён. Он применяется сразу.')
    return await _orig_text(m,bot_instance)
bot.text_handler=text_handler
