import asyncio
from datetime import datetime, timezone, timedelta

import bot as app
from config import UNITS
from db import connect, user
from combat import resolve

COOLDOWN = timedelta(minutes=10)
_PENDING = {}
_ORIGINAL_CONFIRM = app.battle_confirm
_ORIGINAL_DECLINE = app.battle_decline

LINES = [
    '🛰 Разведка...',
    '🛩 БПЛА вышли на боевой курс...',
    '🎯 Перехватчики в воздухе...',
    '🚀 Ракетный удар...',
    '🪖 Пехота вступила в бой...',
    '🚙 БМП открыли огонь...',
    '💥 Артиллерия работает...',
    '🛡 Танки продвигаются вперёд...',
    '🚁 Вертолёты атакуют...',
    '✈️ Самолёты наносят удар...',
    '💥 Передовая линия столкнулась...',
    '🎯 Перехватчик сбит...',
    '🛩 БПЛА уничтожен...',
    '🚙 БМП подбита...',
    '⏳ Последние секунды боя...',
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _money(v):
    return f'{int(v):,}'.replace(',', ' ')


def _kills(kills):
    return '\n'.join(
        f'{unit["title"]}: {int(kills.get(key, 0))}'
        for key, unit in UNITS.items()
    )


async def _edit(bot, chat_id, message_id, text, markup=None):
    if not chat_id or not message_id:
        return False
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=markup,
            parse_mode=None,
        )
        return True
    except Exception as exc:
        print(f'[battle_sync] attacker edit failed: {exc}')
        return False


async def confirm(c, bot):
    attacker_id = int(c.from_user.id)
    target = app.PENDING.get(attacker_id)
    if target is not None and getattr(c, 'message', None) is not None:
        _PENDING[attacker_id] = (
            int(target),
            int(c.message.chat.id),
            int(c.message.message_id),
        )
    return await _ORIGINAL_CONFIRM(c, bot)


async def accept(c, attacker_id, bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)

    if app.INVITES.get(attacker_id) != defender_id:
        return await c.answer('Приглашение уже недействительно.', show_alert=True)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        app.INVITES.pop(attacker_id, None)
        _PENDING.pop(attacker_id, None)
        return await c.answer('Игрок не найден.', show_alert=True)

    def _cd(row):
        raw = row['last_attack'] or ''
        if not raw:
            return 0
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, int((dt + COOLDOWN - datetime.now(timezone.utc)).total_seconds()))
        except Exception:
            return 0

    if _cd(attacker) or _cd(defender):
        app.INVITES.pop(attacker_id, None)
        _PENDING.pop(attacker_id, None)
        return await c.answer('Бой уже недоступен.', show_alert=True)

    app.INVITES.pop(attacker_id, None)
    stored = _PENDING.pop(attacker_id, None)
    if stored and int(stored[0]) == defender_id:
        attacker_chat_id = int(stored[1])
        attacker_message_id = int(stored[2])
    else:
        attacker_chat_id = attacker_id
        attacker_message_id = None

    try:
        await c.answer()
    except Exception:
        pass

    # Exactly the same frame is written to both chats before the countdown.
    first = '⚔️ БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'
    tasks = [c.message.edit_text(first, parse_mode=None)]
    if attacker_message_id:
        tasks.append(_edit(bot, attacker_chat_id, attacker_message_id, first))
    await asyncio.gather(*tasks, return_exceptions=True)

    # One coroutine, one clock, one frame index for both players.
    for i, line in enumerate(LINES):
        text = f'⚔️ БОЙ\n\n{line}\n\n⏱ {15 - i} сек.'
        tasks = [c.message.edit_text(text, parse_mode=None)]
        if attacker_message_id:
            tasks.append(_edit(bot, attacker_chat_id, attacker_message_id, text))
        await asyncio.gather(*tasks, return_exceptions=True)
        if i < len(LINES) - 1:
            await asyncio.sleep(1)

    # The result is calculated only after the last animation frame.
    a_after, d_after, winner, events, kills_a, kills_d = resolve(
        attacker, defender, with_kills=True
    )
    winner_id = attacker_id if winner == 'attacker' else defender_id
    loser_id = defender_id if winner == 'attacker' else attacker_id
    winner_arm = a_after if winner == 'attacker' else d_after
    loser_raw = d_after if winner == 'attacker' else a_after
    loser_before = defender if winner == 'attacker' else attacker
    loser_arm = {k: int(loser_raw[k]) * 80 // 100 for k in UNITS}
    winner_kills = kills_a if winner == 'attacker' else kills_d
    loser_kills = kills_d if winner == 'attacker' else kills_a

    reward = int(sum(winner_kills[k] * UNITS[k]['price'] for k in UNITS) * 0.05)
    loser_reward = int(
        sum(
            (int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price']
            for k in UNITS
        ) * 0.02
    )

    db = await connect()
    try:
        unit_sets = ','.join(f'{k}=?' for k in UNITS)
        kill_sets = ','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(
            f'UPDATE users SET {unit_sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',
            [winner_arm[k] for k in UNITS] + [_now(), winner_id],
        )
        await db.execute(
            f'UPDATE users SET {unit_sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',
            [loser_arm[k] for k in UNITS] + [_now(), loser_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [winner_kills[k] for k in UNITS] + [winner_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [loser_kills[k] for k in UNITS] + [loser_id],
        )
        await db.execute(
            'UPDATE users SET balance=balance+? WHERE user_id=?',
            (reward, winner_id),
        )
        await db.execute(
            'UPDATE users SET balance=balance+? WHERE user_id=?',
            (loser_reward, loser_id),
        )
        await db.commit()
    finally:
        await db.close()

    winner_row = await user(winner_id)
    winner_name = (
        '@' + winner_row['username']
        if winner_row and winner_row['username']
        else f'ID {winner_id}'
    )
    win_text = (
        f'🏆 WIN\n\n'
        f'Победитель: {winner_name}\n'
        f'💰 Награда: ${_money(reward)}\n\n'
        f'🎯 Уничтожено:\n{_kills(winner_kills)}'
    )
    loss_text = (
        f'💀 LOSS\n\n'
        f'🏆 Победитель: {winner_name}\n'
        f'📉 Твоя армия: −20%\n'
        f'💵 Компенсация: ${_money(loser_reward)}\n\n'
        f'🎯 Уничтожено:\n{_kills(loser_kills)}'
    )

    await asyncio.gather(
        c.message.edit_text(
            win_text if winner_id == defender_id else loss_text,
            reply_markup=app.back(),
            parse_mode=None,
        ),
        _edit(
            bot,
            attacker_chat_id,
            attacker_message_id,
            win_text if winner_id == attacker_id else loss_text,
            app.back(),
        ) if attacker_message_id else asyncio.sleep(0),
        return_exceptions=True,
    )


def decline(c, attacker_id, bot):
    return _ORIGINAL_DECLINE(c, attacker_id, bot)
