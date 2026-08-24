from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

EARN_TYPES = {
    'boost': ('🚀 Буст канала / группы', 'earn_boost'),
    'channel': ('📢 Подписка на канал', 'earn_channel'),
    'group': ('👥 Вход в группу', 'earn_group'),
}

def earn_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🚀 Буст канала / группы', callback_data='earn_add:boost')],
        [InlineKeyboardButton(text='📢 Подписка на канал', callback_data='earn_add:channel')],
        [InlineKeyboardButton(text='👥 Вход в группу', callback_data='earn_add:group')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='admin')],
    ])

def earn_player_keyboard(items):
    rows=[]
    for item in items:
        rows.append([InlineKeyboardButton(text=f"{item['title']} · +${int(item['reward']):,}".replace(',', ' '), url=item['url'])])
        rows.append([InlineKeyboardButton(text='✅ Проверить выполнение', callback_data=f"earn_check:{item['kind']}:{item['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text='⬅️ Назад',callback_data='home')]])

def parse_earn_command(text, command):
    parts=text.strip().split()
    if len(parts)!=3 or parts[0].lower()!=command:
        return None, f'Формат: {command} <ссылка> <сумма>'
    url=parts[1].strip()
    if not (url.startswith('https://t.me/') or url.startswith('http://t.me/')):
        return None, 'Ссылка должна быть Telegram-ссылкой: https://t.me/...'
    try: reward=int(parts[2])
    except ValueError: return None, 'Сумма должна быть целым числом.'
    if reward<=0 or reward>2_000_000_000: return None, 'Некорректная сумма награды.'
    return (url,reward),None
