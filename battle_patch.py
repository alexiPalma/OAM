import asyncio
from datetime import datetime, timezone, timedelta
from config import UNITS
from db import connect, user
from combat import resolve

BATTLE_COOLDOWN = timedelta(minutes=10)
SYNC_INVITES = {}

BATTLE_LINES = [
    '⚔️ Идёт бой',
    '💥 Гремят взрывы',
    '🪖 Пехота зачищает позиции',
    '🔥 Раздаются выстрелы',
    '🌫 Над полем боя поднимается дым',
    '⚡ Ударная волна проходит по позиции',
    '🪖 Подразделения продвигаются вперёд',
    '💥 На линии фронта новый взрыв',
    '🏴 Позиции сторон меняются',
    '⚔️ Бой продолжается',
]


def _now():
    return datetime.now(timezone.utc)


def _cd(u):
    raw = u['last_attack'] or ''
    if not raw:
        return 0
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((dt + BATTLE_COOLDOWN - _now()).total_seconds()))
    except Exception:
        return 0


def _money(v):
    return f'{int(v):,}'.replace(',', ' ')


def _kb(rows):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b) for a, b in row] for row in rows])


async def _edit(bot, chat_id, message_id, text, markup=None):
    if not message_id:
        return
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=markup, parse_mode=None)
    except Exception:
        pass


async def _sync_accept(c, attacker_id, bot, original_accept):
    attacker_id = int(attacker_id)
    defender_id = c.from_user.id
    bot_module = __import__('bot')
    invites = bot_module.INVITES

    if invites.get(attacker_id) != defender_id:
        return await original_accept(c, attacker_id, bot)

    me = await user(attacker_id)
    opp = await user(defender_id)
    if not me or not opp or _cd(me) or _cd(opp):
        invites.pop(attacker_id, None)
        SYNC_INVITES.pop(attacker_id, None)
        return await c.answer('Бой уже недоступен.', show_alert=True)

    invites.pop(attacker_id, None)
    stored = SYNC_INVITES.pop(attacker_id, None)
    attacker_message_id = stored[1] if stored and stored[0] == defender_id else None

    # Оба игрока начинают с одного и того же кадра. Старое сообщение
    # нападающего «ожидаем решения» НЕ остаётся висеть отдельным сообщением.
    first = '⚔️ WorldWarDynasty • БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'
    await asyncio.gather(
        _edit(bot, attacker_id, attacker_message_id, first),
        c.message.edit_text(first, parse_mode=None),
        return_exceptions=True,
    )

    # Одна общая последовательность. Один индекс = один кадр для обоих.
    for i in range(15):
        text = f'⚔️ WorldWarDynasty • БОЙ\n\n{BATTLE_LINES[i % len(BATTLE_LINES)]}\n\n⏱ {15 - i} сек.'
        tasks = [c.message.edit_text(text, parse_mode=None)]
        if attacker_message_id:
            tasks.append(_edit(bot, attacker_id, attacker_message_id, text))
        await asyncio.gather(*tasks, return_exceptions=True)
        if i < 14:
            await asyncio.sleep(1)

    # Только после последнего кадра рассчитываем и записываем результат.
    a_after, d_after, winner, events, kills_a, kills_d = resolve(me, opp, with_kills=True)
    winner_id = attacker_id if winner == 'attacker' else defender_id
    loser_id = defender_id if winner == 'attacker' else attacker_id
    winner_arm = a_after if winner == 'attacker' else d_after
    loser_raw = d_after if winner == 'attacker' else a_after
    loser_source = opp if winner == 'attacker' else me
    loser_arm = {k: int(loser_raw[k]) * 80 // 100 for k in UNITS}
    winner_k = kills_a if winner == 'attacker' else kills_d
    loser_k = kills_d if winner == 'attacker' else kills_a
    reward = int(sum(winner_k[k] * UNITS[k]['price'] for k in UNITS) * 0.05)
    loser_reward = int(sum((int(loser_source[k]) - loser_arm[k]) * UNITS[k]['price'] for k in UNITS) * 0.02)

    db = await connect()
    sets = ', '.join(f'{k}=?' for k in UNITS)
    ksets = ', '.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
    await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?', [winner_arm[k] for k in UNITS] + [_now().isoformat(), winner_id])
    await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?', [loser_arm[k] for k in UNITS] + [_now().isoformat(), loser_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?', [winner_k[k] for k in UNITS] + [winner_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?', [loser_k[k] for k in UNITS] + [loser_id])
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (reward, winner_id))
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (loser_reward, loser_id))
    await db.commit()
    await db.close()

    titles = {
        'soldier': '🪖 Пехота', 'interceptor': '🎯 Перехватчики', 'drone': '🛩 БПЛА',
        'bmp': '🚙 БМП', 'tank': '🛡 Танки', 'helicopter': '🚁 Вертолёты',
        'plane': '✈️ Самолёты', 'missile': '🚀 Ракеты', 'artillery': '💥 Артиллерия'
    }
    winner_kills = '\n'.join(f'{titles[k]}: {int(winner_k.get(k, 0))}' for k in titles)
    loser_kills = '\n'.join(f'{titles[k]}: {int(loser_k.get(k, 0))}' for k in titles)
    wn = await user(winner_id)
    winner_name = '@' + wn['username'] if wn['username'] else f'ID {winner_id}'

    wintext = f'🏆 WIN\n\nПобедитель: {winner_name}\n💰 Награда: ${_money(reward)}\n\n🎯 Уничтожено:\n{winner_kills}'
    losstext = f'💀 LOSS\n\n🏆 Победитель: {winner_name}\n📉 Твоя армия: −20%\n💵 Компенсация: ${_money(loser_reward)}\n\n🎯 Уничтожено:\n{loser_kills}'
    markup = _kb([[('⬅️ Назад', 'home')]])

    # Результат тоже появляется только после окончания общей анимации.
    await asyncio.gather(
        _edit(bot, attacker_id, attacker_message_id, wintext if winner_id == attacker_id else losstext, markup if winner_id == attacker_id or loser_id == attacker_id else None),
        c.message.edit_text(wintext if winner_id == defender_id else losstext, reply_markup=markup, parse_mode=None),
        return_exceptions=True,
    )



def install(bot_module):
    # ВАЖНО: патчим именно battle_accept, потому что именно он вызывается
    # кнопкой accept:<id>. Старые патчи меняли battle_confirm, поэтому на
    # реальный момент принятия боя вообще не воздействовали.
    original_accept = bot_module.battle_accept
    original_confirm = bot_module.battle_confirm

    async def synced_confirm(c, bot):
        attacker_id = c.from_user.id
        target = bot_module.PENDING.get(attacker_id)
        result = await original_confirm(c, bot)
        # original_confirm уже создал INVITES и отредактировал сообщение
        # нападающего. Запоминаем именно это сообщение, чтобы при принятии
        # боя редактировать его, а не отправлять новое.
        if target is not None and bot_module.INVITES.get(attacker_id) is not None:
            SYNC_INVITES[attacker_id] = (int(target), c.message.message_id)
        return result

    async def synced_accept(c, attacker_id, bot):
        return await _sync_accept(c, attacker_id, bot, original_accept)

    bot_module.battle_confirm = synced_confirm
    bot_module.battle_accept = synced_accept
