"""OAM SINGLE ENTRYPOINT.

Run this file directly. It owns the dispatcher and the complete battle flow.
The old launcher/callback chain is deliberately not used for battle actions.
"""
import asyncio
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import achievements
import bot as app
import run
from config import ADMIN_ID, BOT_TOKEN, OWNER_ID2, UNITS
from db import connect, init_db, user
from settings import init_settings
from combat import resolve

BATTLE_TTL = timedelta(seconds=60)
BATTLE_LINES = [
    '⚔️ Идёт бой', '💥 Гремят взрывы', '🪖 Пехота зачищает позиции',
    '🔥 Раздаются выстрелы', '🌫 Над полем боя поднимается дым',
    '⚡ Ударная волна проходит по позиции', '🚙 БМП открыли огонь',
    '💥 Артиллерия работает', '🛡 Танки продвигаются вперёд',
    '🚁 Вертолёты атакуют', '✈️ Самолёты наносят удар', '🚀 Ракетный удар',
    '🛰 Последняя атака', '⏳ Последние секунды боя', '🏆 Бой завершён',
]

# fix.py owns the invitation lifecycle. No second battle module is authoritative.
INVITES = {}


def now():
    return datetime.now(timezone.utc)


def money(v):
    return f'{int(v):,}'.replace(',', ' ')


def kills_text(kills):
    return '\n'.join(f'{UNITS[k]["title"]}: {int(kills.get(k, 0))}' for k in UNITS)


async def edit_message(bot, chat_id, message_id, text, markup=None):
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text,
            reply_markup=markup, parse_mode=None,
        )
    except Exception as exc:
        print(f'[OAM FIX] edit failed chat={chat_id} message={message_id}: {exc}')


def invite_is_valid(attacker_id, defender_id):
    item = INVITES.get(int(attacker_id))
    if not item or int(item['defender_id']) != int(defender_id):
        return False
    if now() - item['created_at'] > BATTLE_TTL:
        INVITES.pop(int(attacker_id), None)
        return False
    return True


async def battle_confirm(c, bot):
    attacker_id = int(c.from_user.id)
    defender_id = app.PENDING.get(attacker_id)
    if not defender_id:
        return await c.answer('Сначала выберите противника.', show_alert=True)
    defender_id = int(defender_id)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        app.PENDING.pop(attacker_id, None)
        return await c.answer('Бой сейчас недоступен.', show_alert=True)

    app.PENDING.pop(attacker_id, None)
    if attacker_id in INVITES:
        return await c.answer('⏳ У вас уже есть ожидающий запрос на бой.', show_alert=True)

    # The invitation is created BEFORE send_message and is never delegated to
    # bot.py/battle_force_sync.py. Therefore the accept button always points at
    # the state that this very process owns.
    INVITES[attacker_id] = {
        'defender_id': defender_id,
        'created_at': now(),
        'attacker_chat_id': int(c.message.chat.id),
        'attacker_message_id': int(c.message.message_id),
    }
    # Compatibility only for legacy decline helpers; accept never reads this.
    app.INVITES[attacker_id] = defender_id

    attacker_name = '@' + attacker['username'] if attacker['username'] else f'ID {attacker_id}'
    text = (
        '⚔️ WORLDWAR DYNASTY • НА ВАС НАПАЛИ\n\n'
        f'👤 Нападающий: {attacker_name}\n\n'
        f'{app.army_text(attacker)}\n\nПримите бой или откажитесь.'
    )
    keyboard = app.kb([
        [('⚔️ ПРИНЯТЬ БОЙ', f'accept:{attacker_id}')],
        [('🏳️ ОТКАЗАТЬСЯ', f'decline:{attacker_id}')],
    ])

    try:
        await bot.send_message(defender_id, text, reply_markup=keyboard)
    except Exception as exc:
        INVITES.pop(attacker_id, None)
        app.INVITES.pop(attacker_id, None)
        return await c.answer(f'Не удалось отправить приглашение: {exc}', show_alert=True)

    await c.answer()
    await app.safe(c, '⏳ Запрос на бой отправлен противнику. Ожидаем решения...', app.back('attack'))


async def battle_decline(c, attacker_id, bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    if not invite_is_valid(attacker_id, defender_id):
        return await c.answer('Предложение уже недействительно.', show_alert=True)
    # app.battle_decline expects the legacy dictionary, so keep it populated
    # until that function has finished.
    try:
        return await app.battle_decline(c, attacker_id, bot)
    finally:
        INVITES.pop(attacker_id, None)
        app.INVITES.pop(attacker_id, None)


async def battle_accept(c, attacker_id, bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    invite = INVITES.get(attacker_id)
    if not invite_is_valid(attacker_id, defender_id):
        return await c.answer('Предложение уже недействительно.', show_alert=True)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        INVITES.pop(attacker_id, None)
        app.INVITES.pop(attacker_id, None)
        return await c.answer('Игрок не найден.', show_alert=True)

    INVITES.pop(attacker_id, None)
    app.INVITES.pop(attacker_id, None)
    try:
        await c.answer()
    except Exception:
        pass

    attacker_chat_id = invite['attacker_chat_id']
    attacker_message_id = invite['attacker_message_id']

    # One coroutine + one frame index = one clock for both players.
    start_text = '⚔️ БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'
    await asyncio.gather(
        c.message.edit_text(start_text, parse_mode=None),
        edit_message(bot, attacker_chat_id, attacker_message_id, start_text),
        return_exceptions=True,
    )

    total = 15
    for i in range(total):
        frame = f'⚔️ БОЙ\n\n{BATTLE_LINES[i % len(BATTLE_LINES)]}\n\n⏱ {total - i} сек.'
        await asyncio.gather(
            c.message.edit_text(frame, parse_mode=None),
            edit_message(bot, attacker_chat_id, attacker_message_id, frame),
            return_exceptions=True,
        )
        if i < total - 1:
            await asyncio.sleep(1)

    a_after, d_after, winner, events, kills_a, kills_d = resolve(attacker, defender, with_kills=True)
    winner_id = attacker_id if winner == 'attacker' else defender_id
    loser_id = defender_id if winner == 'attacker' else attacker_id
    winner_arm = a_after if winner == 'attacker' else d_after
    loser_raw = d_after if winner == 'attacker' else a_after
    loser_before = defender if winner == 'attacker' else attacker
    loser_arm = {k: int(loser_raw[k]) * 80 // 100 for k in UNITS}
    winner_kills = kills_a if winner == 'attacker' else kills_d
    loser_kills = kills_d if winner == 'attacker' else kills_a
    reward = int(sum(winner_kills[k] * UNITS[k]['price'] for k in UNITS) * 0.05)
    loser_reward = int(sum((int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price'] for k in UNITS) * 0.02)

    db = await connect()
    try:
        sets = ','.join(f'{k}=?' for k in UNITS)
        kill_sets = ','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?', [winner_arm[k] for k in UNITS] + [now().isoformat(), winner_id])
        await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?', [loser_arm[k] for k in UNITS] + [now().isoformat(), loser_id])
        await db.execute(f'UPDATE users SET {kill_sets} WHERE user_id=?', [winner_kills[k] for k in UNITS] + [winner_id])
        await db.execute(f'UPDATE users SET {kill_sets} WHERE user_id=?', [loser_kills[k] for k in UNITS] + [loser_id])
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (reward, winner_id))
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (loser_reward, loser_id))
        await db.commit()
    finally:
        await db.close()

    winner_row = await user(winner_id)
    winner_name = '@' + winner_row['username'] if winner_row and winner_row['username'] else f'ID {winner_id}'
    win_text = f'🏆 WIN\n\nПобедитель: {winner_name}\n💰 Награда: ${money(reward)}\n\n🎯 Уничтожено:\n{kills_text(winner_kills)}'
    loss_text = f'💀 LOSS\n\nПобедитель: {winner_name}\n📉 Твоя армия: −20%\n💵 Компенсация: ${money(loser_reward)}\n\n🎯 Уничтожено:\n{kills_text(loser_kills)}'

    await asyncio.gather(
        c.message.edit_text(win_text if winner_id == defender_id else loss_text, reply_markup=app.back(), parse_mode=None),
        edit_message(bot, attacker_chat_id, attacker_message_id, win_text if winner_id == attacker_id else loss_text, app.back()),
        return_exceptions=True,
    )


async def callback(c, bot):
    data = c.data or ''
    if data == 'battle_confirm':
        return await battle_confirm(c, bot)
    if data.startswith('accept:'):
        try:
            return await battle_accept(c, int(data.split(':', 1)[1]), bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)
    if data.startswith('decline:'):
        try:
            return await battle_decline(c, int(data.split(':', 1)[1]), bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)
    return await run.callback(c, bot)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is empty')
    await init_db()
    await init_settings(ADMIN_ID)
    db = await connect()
    try:
        await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (ADMIN_ID,))
        if OWNER_ID2:
            await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (OWNER_ID2,))
        await db.commit()
    finally:
        await db.close()

    await achievements.init_achievements()
    try:
        achievements.install_sync()
    except Exception as exc:
        print(f'[OAM FIX] achievements hook skipped: {exc}')

    tg = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(run.start_wrapper, CommandStart())
    dp.message.register(run.text_handler, F.text)
    dp.callback_query.register(callback, F.data)

    print('[OAM FIX] SINGLE ENTRYPOINT: fix.py')
    print('[OAM FIX] battle invitations are owned by fix.py')
    print('[OAM FIX] both players share one 15-second animation clock')
    print('[OAM FIX] result appears only after the final frame')
    await dp.start_polling(tg)


if __name__ == '__main__':
    asyncio.run(main())
