"""Final synchronized battle patch.

The accepted battle uses exactly two existing Telegram messages: the
attacker's waiting message and the defender's invitation message. One shared
15-frame loop edits both messages, then both are replaced by their results.
"""
import asyncio
from datetime import datetime, timezone

import bot as app
from config import UNITS
from db import connect, user
from combat import resolve

_PENDING_MESSAGES = {}

BATTLE_LINES = [
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


def _money(value):
    return f'{int(value):,}'.replace(',', ' ')


def _kills_text(kills):
    # Every unit is printed, including zero.
    return '\n'.join(
        f'{unit["title"]}: {int(kills.get(key, 0))}'
        for key, unit in UNITS.items()
    )


async def _edit(tg_bot, chat_id, message_id, text, markup=None):
    if not message_id:
        return
    try:
        await tg_bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=markup,
            parse_mode=None,
        )
    except Exception:
        pass


async def _confirm_wrapper(c, tg_bot, original_confirm):
    attacker_id = c.from_user.id
    target = app.PENDING.get(attacker_id)
    result = await original_confirm(c, tg_bot)
    # original_confirm changes the attacker's exact message to the waiting
    # state. Save that message id for battle_accept.
    if target is not None and app.INVITES.get(attacker_id) == target:
        _PENDING_MESSAGES[attacker_id] = (int(target), c.message.message_id)
    return result


async def battle_accept(c, attacker_id, tg_bot):
    attacker_id = int(attacker_id)
    defender_id = c.from_user.id
    if app.INVITES.get(attacker_id) != defender_id:
        return await c.answer('Приглашение уже недействительно.', show_alert=True)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        app.INVITES.pop(attacker_id, None)
        _PENDING_MESSAGES.pop(attacker_id, None)
        return await c.answer('Игрок не найден.', show_alert=True)

    app.INVITES.pop(attacker_id, None)
    stored = _PENDING_MESSAGES.pop(attacker_id, None)
    attacker_message_id = stored[1] if stored and stored[0] == defender_id else None

    try:
        await c.answer()
    except Exception:
        pass

    # Both players enter the animation at the same time and from the same
    # shared coroutine. The attacker does NOT receive a second message.
    first = '⚔️ БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'
    await asyncio.gather(
        _edit(tg_bot, attacker_id, attacker_message_id, first),
        c.message.edit_text(first, parse_mode=None),
        return_exceptions=True,
    )

    for i, line in enumerate(BATTLE_LINES):
        text = f'⚔️ БОЙ\n\n{line}\n\n⏱ {15 - i} сек.'
        await asyncio.gather(
            _edit(tg_bot, attacker_id, attacker_message_id, text),
            c.message.edit_text(text, parse_mode=None),
            return_exceptions=True,
        )
        if i < len(BATTLE_LINES) - 1:
            await asyncio.sleep(1)

    # Resolve only after the common 15-frame animation has ended.
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
    loser_reward = int(sum(
        (int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price']
        for k in UNITS
    ) * 0.02)

    db = await connect()
    try:
        unit_cols = ','.join(f'{k}=?' for k in UNITS)
        kill_cols = ','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(
            f'UPDATE users SET {unit_cols},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',
            [winner_arm[k] for k in UNITS] + [_now(), winner_id],
        )
        await db.execute(
            f'UPDATE users SET {unit_cols},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',
            [loser_arm[k] for k in UNITS] + [_now(), loser_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_cols} WHERE user_id=?',
            [winner_kills[k] for k in UNITS] + [winner_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_cols} WHERE user_id=?',
            [loser_kills[k] for k in UNITS] + [loser_id],
        )
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (reward, winner_id))
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (loser_reward, loser_id))
        await db.commit()
    finally:
        await db.close()

    try:
        import achievements
        await achievements.check(winner_id, tg_bot, notify=True)
        await achievements.check(loser_id, tg_bot, notify=True)
    except Exception:
        pass

    winner_row = await user(winner_id)
    winner_name = '@' + winner_row['username'] if winner_row and winner_row['username'] else f'ID {winner_id}'
    winner_kill_text = _kills_text(winner_kills)
    loser_kill_text = _kills_text(loser_kills)

    win_default = (
        f'🏆 WIN\n\nПобедитель: {winner_name}\n'
        f'💰 Награда: ${_money(reward)}\n\n'
        f'💥 УНИЧТОЖЕНО ТОБОЙ:\n{winner_kill_text}'
    )
    loss_default = (
        f'💀 LOSS\n\n🏆 Победитель: {winner_name}\n'
        f'📉 Твоя армия: −20%\n'
        f'💵 Компенсация: ${_money(loser_reward)}\n\n'
        f'💥 УНИЧТОЖЕНО ТОБОЙ:\n{loser_kill_text}'
    )

    try:
        win_text = await app.tpl('win', win_default, winner=winner_name, reward=_money(reward), kills=winner_kill_text)
    except Exception:
        win_text = win_default
    try:
        loss_text = await app.tpl('loss', loss_default, winner=winner_name, loss='20%', reward=_money(loser_reward), kills=loser_kill_text)
    except Exception:
        loss_text = loss_default

    # Replace the SAME two messages with the final results.
    await asyncio.gather(
        _edit(
            tg_bot, attacker_id, attacker_message_id,
            win_text if winner_id == attacker_id else loss_text,
            app.back(),
        ),
        c.message.edit_text(
            win_text if winner_id == defender_id else loss_text,
            reply_markup=app.back(),
            parse_mode=None,
        ),
        return_exceptions=True,
    )


def install(bot_module=app):
    # Patch BOTH callbacks. Capturing the attacker's message in
    # battle_confirm is required for true synchronization.
    original_confirm = bot_module.battle_confirm

    async def patched_confirm(c, tg_bot):
        return await _confirm_wrapper(c, tg_bot, original_confirm)

    bot_module.battle_confirm = patched_confirm
    bot_module.battle_accept = battle_accept
