from datetime import datetime, timezone
import asyncio

import bot as app
from db import connect, user
from config import UNITS
from combat import resolve


def _now():
    return datetime.now(timezone.utc).isoformat()


def _money(value):
    return f'{int(value):,}'.replace(',', ' ')


def _kills_text(kills):
    rows = []
    for key, unit in UNITS.items():
        amount = int(kills.get(key, 0))
        if amount:
            rows.append(f'{unit["title"]}: {amount}')
    return '\n'.join(rows) if rows else 'Ничего не уничтожено.'


async def battle_accept(c, attacker_id, tg_bot):
    attacker_id = int(attacker_id)
    defender_id = c.from_user.id
    if app.INVITES.get(attacker_id) != defender_id:
        return await c.answer('Приглашение уже недействительно.', show_alert=True)

    app.INVITES.pop(attacker_id, None)
    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        return await c.answer('Игрок не найден.', show_alert=True)

    attacker_name = '@' + attacker['username'] if attacker['username'] else f'ID {attacker_id}'
    defender_name = '@' + defender['username'] if defender['username'] else f'ID {defender_id}'

    try:
        await c.message.edit_text('⚔️ БОЙ НАЧАЛСЯ\n\n🛰 Разведка...')
    except Exception:
        pass
    try:
        await c.answer()
    except Exception:
        pass

    try:
        attacker_msg = await tg_bot.send_message(
            attacker_id,
            f'⚔️ БОЙ\n\n👤 Ты атаковал: {defender_name}\n\n🛰 Разведка...'
        )
    except Exception:
        attacker_msg = None

    battle_lines = [
        '⚔️ БОЙ\n\n🛰 Разведка...',
        '⚔️ БОЙ\n\n🛩 БПЛА вышли на боевой курс...',
        '⚔️ БОЙ\n\n🎯 Перехватчики в воздухе...',
        '⚔️ БОЙ\n\n🚀 Ракетный удар...',
        '⚔️ БОЙ\n\n🪖 Пехота вступила в бой...',
        '⚔️ БОЙ\n\n🚙 БМП открыли огонь...',
        '⚔️ БОЙ\n\n💥 Артиллерия работает...',
        '⚔️ БОЙ\n\n🛡 Танки продвигаются вперёд...',
        '⚔️ БОЙ\n\n🚁 Вертолёты атакуют...',
        '⚔️ БОЙ\n\n✈️ Самолёты наносят удар...',
        '⚔️ БОЙ\n\n💥 Передовая линия столкнулась...',
        '⚔️ БОЙ\n\n🎯 Перехватчик сбит...',
        '⚔️ БОЙ\n\n🛩 БПЛА уничтожен...',
        '⚔️ БОЙ\n\n🚙 БМП подбита...',
        '⚔️ БОЙ\n\n⏳ Последние секунды боя...'
    ]

    for text in battle_lines:
        try:
            await c.message.edit_text(text)
        except Exception:
            pass
        if attacker_msg:
            try:
                await attacker_msg.edit_text(text)
            except Exception:
                pass
        await asyncio.sleep(1)

    # The combat engine contains the artillery rules. In particular:
    # - artillery does not counter artillery;
    # - soldiers and interceptors do not counter artillery;
    # - normal artillery counters are reduced by 25%.
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
            [winner_arm[k] for k in UNITS] + [_now(), winner_id]
        )
        await db.execute(
            f'UPDATE users SET {unit_cols},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',
            [loser_arm[k] for k in UNITS] + [_now(), loser_id]
        )
        # Record kills for BOTH sides so artillery kills count toward achievements
        # no matter which side won.
        await db.execute(
            f'UPDATE users SET {kill_cols} WHERE user_id=?',
            [winner_kills[k] for k in UNITS] + [winner_id]
        )
        await db.execute(
            f'UPDATE users SET {kill_cols} WHERE user_id=?',
            [loser_kills[k] for k in UNITS] + [loser_id]
        )
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (reward, winner_id))
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (loser_reward, loser_id))
        await db.commit()
    finally:
        await db.close()

    # Re-check achievements immediately so artillery progress can unlock an
    # achievement right after the battle instead of waiting for the next menu.
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

    if winner == 'attacker':
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
    else:
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
        win_text = await app.tpl(
            'win', win_default,
            winner=winner_name,
            reward=_money(reward),
            kills=winner_kill_text,
        )
    except Exception:
        win_text = win_default

    try:
        loss_text = await app.tpl(
            'loss', loss_default,
            winner=winner_name,
            loss='20%',
            reward=_money(loser_reward),
            kills=loser_kill_text,
        )
    except Exception:
        loss_text = loss_default

    try:
        await tg_bot.send_message(winner_id, win_text, reply_markup=app.back())
        await tg_bot.send_message(loser_id, loss_text, reply_markup=app.back())
    except Exception:
        pass


def install(bot_module=app):
    bot_module.battle_accept = battle_accept
