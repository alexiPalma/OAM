"""Authoritative synchronized battle handler.

The important part here is that the attacker's message ID is captured BEFORE
calling the original confirmation handler. That removes the race/lookup issue
that caused the attacker to remain on the waiting screen while the defender
was watching the 15-second animation.
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
    return '\n'.join(f'{unit["title"]}: {int(kills.get(key, 0))}' for key, unit in UNITS.items())

async def _edit(tg_bot, chat_id, message_id, text, markup=None):
    if not message_id:
        return False
    try:
        await tg_bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=markup,
            parse_mode=None,
        )
        return True
    except Exception as exc:
        print(f'[WWD battle] attacker edit failed: {exc}')
        return False

async def _confirm_wrapper(c, tg_bot, original_confirm):
    attacker_id = int(c.from_user.id)
    target = app.PENDING.get(attacker_id)

    # Capture the exact Telegram message BEFORE original_confirm can edit it.
    # This is the message the attacker must see during the same animation.
    if target is not None and getattr(c, 'message', None) is not None:
        _PENDING_MESSAGES[attacker_id] = (
            int(target),
            int(c.message.chat.id),
            int(c.message.message_id),
        )

    return await original_confirm(c, tg_bot)

async def battle_accept(c, attacker_id, tg_bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)

    if app.INVITES.get(attacker_id) != defender_id:
        return await c.answer('Приглашение уже недействительно.', show_alert=True)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        app.INVITES.pop(attacker_id, None)
        _PENDING_MESSAGES.pop(attacker_id, None)
        return await c.answer('Игрок не найден.', show_alert=True)

    # Consume invitation exactly once.
    app.INVITES.pop(attacker_id, None)
    stored = _PENDING_MESSAGES.pop(attacker_id, None)
    attacker_chat_id = None
    attacker_message_id = None
    if stored and int(stored[0]) == defender_id:
        attacker_chat_id = int(stored[1])
        attacker_message_id = int(stored[2])

    try:
        await c.answer()
    except Exception:
        pass

    first = '⚔️ БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'

    # Both messages receive the FIRST frame together.
    tasks = [c.message.edit_text(first, parse_mode=None)]
    if attacker_chat_id and attacker_message_id:
        tasks.append(_edit(tg_bot, attacker_chat_id, attacker_message_id, first))
    await asyncio.gather(*tasks, return_exceptions=True)

    # One shared clock/frame sequence. There is no separate sleep for either
    # player, so both sides always advance through the same frame number.
    for i in range(15):
        text = (
            '⚔️ БОЙ\n\n'
            f'{BATTLE_LINES[i]}\n\n'
            f'⏱ {15 - i} сек.'
        )
        tasks = [c.message.edit_text(text, parse_mode=None)]
        if attacker_chat_id and attacker_message_id:
            tasks.append(_edit(tg_bot, attacker_chat_id, attacker_message_id, text))
        await asyncio.gather(*tasks, return_exceptions=True)
        if i < 14:
            await asyncio.sleep(1)

    # Calculate and save the result only after the shared animation finishes.
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
        sum((int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price'] for k in UNITS) * 0.02
    )

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

    try:
        import achievements
        await achievements.check(winner_id, tg_bot, notify=True)
        await achievements.check(loser_id, tg_bot, notify=True)
    except Exception:
        pass

    winner_row = await user(winner_id)
    winner_name = (
        '@' + winner_row['username']
        if winner_row and winner_row['username']
        else f'ID {winner_id}'
    )

    win_default = (
        f'🏆 WIN\n\n'
        f'Победитель: {winner_name}\n'
        f'💰 Награда: ${_money(reward)}\n\n'
        f'💥 УНИЧТОЖЕНО ТОБОЙ:\n{_kills_text(winner_kills)}'
    )
    loss_default = (
        f'💀 LOSS\n\n'
        f'🏆 Победитель: {winner_name}\n'
        f'📉 Твоя армия: −20%\n'
        f'💵 Компенсация: ${_money(loser_reward)}\n\n'
        f'💥 УНИЧТОЖЕНО ТОБОЙ:\n{_kills_text(loser_kills)}'
    )

    try:
        win_text = await app.tpl(
            'win', win_default,
            winner=winner_name,
            reward=_money(reward),
            kills=_kills_text(winner_kills),
        )
    except Exception:
        win_text = win_default
    try:
        loss_text = await app.tpl(
            'loss', loss_default,
            winner=winner_name,
            loss='20%',
            reward=_money(loser_reward),
            kills=_kills_text(loser_kills),
        )
    except Exception:
        loss_text = loss_default

    # Final result is also sent to both sides together.
    attacker_result = win_text if winner_id == attacker_id else loss_text
    defender_result = win_text if winner_id == defender_id else loss_text
    await asyncio.gather(
        c.message.edit_text(
            defender_result,
            reply_markup=app.back(),
            parse_mode=None,
        ),
        _edit(
            tg_bot,
            attacker_chat_id,
            attacker_message_id,
            attacker_result,
            app.back(),
        ) if attacker_chat_id and attacker_message_id else asyncio.sleep(0),
        return_exceptions=True,
    )


def install(bot_module=app):
    # Install only once, but always replace the real battle_accept handler.
    if getattr(bot_module, '_wwd_battle_rules_installed', False):
        return

    original_confirm = bot_module.battle_confirm
    bot_module.battle_confirm = lambda c, tg_bot: _confirm_wrapper(
        c, tg_bot, original_confirm
    )
    bot_module.battle_accept = battle_accept
    bot_module._wwd_battle_rules_installed = True

install(app)
