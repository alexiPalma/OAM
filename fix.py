"""OAM FIX - single battle entrypoint.

This is the only runtime entrypoint for the patched battle flow.
Both players share one 15-second clock, every frame is written to both
messages, and the result is written only after the final frame.
"""
import asyncio
import inspect
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import achievements
import bot as app
import run
from config import ADMIN_ID, BOT_TOKEN, OWNER_ID2, UNITS
from db import connect, init_db, user
from settings import init_settings
from combat import resolve

BATTLE_LINES = [
    '⚔️ Идёт бой', '💥 Гремят взрывы', '🪖 Пехота зачищает позиции',
    '🔥 Раздаются выстрелы', '🌫 Над полем боя поднимается дым',
    '⚡ Ударная волна проходит по позиции', '🚙 БМП открыли огонь',
    '💥 Артиллерия работает', '🛡 Танки продвигаются вперёд',
    '🚁 Вертолёты атакуют', '✈️ Самолёты наносят удар', '🚀 Ракетный удар',
    '🛰 Последняя атака', '⏳ Последние секунды боя', '🏆 Бой завершён',
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    return f'{int(value):,}'.replace(',', ' ')


def kills_text(kills):
    return '\n'.join(
        f'{UNITS[key]["title"]}: {int((kills or {}).get(key, 0))}'
        for key in UNITS
    )


async def ensure_battle_table():
    db = await connect()
    try:
        await db.execute('''CREATE TABLE IF NOT EXISTS oam_battle_invites (
            attacker_id INTEGER PRIMARY KEY,
            defender_id INTEGER NOT NULL,
            attacker_chat_id INTEGER NOT NULL,
            attacker_message_id INTEGER NOT NULL,
            defender_chat_id INTEGER NOT NULL,
            defender_message_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            running INTEGER NOT NULL DEFAULT 0
        )''')
        await db.commit()
    finally:
        await db.close()


async def get_invite(attacker_id, defender_id):
    db = await connect()
    try:
        cur = await db.execute(
            '''SELECT attacker_id, defender_id, attacker_chat_id, attacker_message_id,
                      defender_chat_id, defender_message_id, created_at, running
               FROM oam_battle_invites WHERE attacker_id=? AND defender_id=?''',
            (int(attacker_id), int(defender_id)),
        )
        return await cur.fetchone()
    finally:
        await db.close()


async def delete_invite(attacker_id):
    db = await connect()
    try:
        await db.execute('DELETE FROM oam_battle_invites WHERE attacker_id=?', (int(attacker_id),))
        await db.commit()
    finally:
        await db.close()


async def reserve_invite(attacker_id, defender_id):
    db = await connect()
    try:
        cur = await db.execute(
            '''UPDATE oam_battle_invites SET running=1
               WHERE attacker_id=? AND defender_id=? AND running=0''',
            (int(attacker_id), int(defender_id)),
        )
        await db.commit()
        if cur.rowcount != 1:
            return None
        cur = await db.execute(
            '''SELECT attacker_id, defender_id, attacker_chat_id, attacker_message_id,
                      defender_chat_id, defender_message_id, created_at, running
               FROM oam_battle_invites WHERE attacker_id=? AND defender_id=?''',
            (int(attacker_id), int(defender_id)),
        )
        return await cur.fetchone()
    finally:
        await db.close()


async def edit_existing(bot: Bot, chat_id, message_id, text, markup=None):
    try:
        await bot.edit_message_text(
            chat_id=int(chat_id), message_id=int(message_id), text=text,
            reply_markup=markup, parse_mode=None,
        )
        return True
    except Exception as exc:
        print(f'[OAM FIX] edit failed {chat_id}/{message_id}: {exc}')
        return False


async def battle_confirm(c, bot: Bot):
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

    db = await connect()
    try:
        cur = await db.execute('SELECT running FROM oam_battle_invites WHERE attacker_id=?', (attacker_id,))
        if await cur.fetchone():
            return await c.answer('⏳ У вас уже есть ожидающий запрос на бой.', show_alert=True)
    finally:
        await db.close()

    attacker_name = '@' + attacker['username'] if attacker['username'] else f'ID {attacker_id}'
    text = (
        '⚔️ WORLDWAR DYNASTY • НА ВАС НАПАЛИ\n\n'
        f'👤 Нападающий: {attacker_name}\n\n{app.army_text(attacker)}\n\n'
        'Примите бой или откажитесь.'
    )
    keyboard = app.kb([
        [('⚔️ ПРИНЯТЬ БОЙ', f'oam_accept:{attacker_id}')],
        [('🏳️ ОТКАЗАТЬСЯ', f'oam_decline:{attacker_id}')],
    ])

    try:
        defender_message = await bot.send_message(defender_id, text, reply_markup=keyboard)
    except Exception as exc:
        return await c.answer(f'Не удалось отправить приглашение: {exc}', show_alert=True)

    db = await connect()
    try:
        await db.execute(
            '''INSERT OR REPLACE INTO oam_battle_invites
               (attacker_id, defender_id, attacker_chat_id, attacker_message_id,
                defender_chat_id, defender_message_id, created_at, running)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
            (attacker_id, defender_id, int(c.message.chat.id), int(c.message.message_id),
             defender_id, int(defender_message.message_id), now_iso()),
        )
        await db.commit()
    finally:
        await db.close()

    await c.answer()
    return await app.safe(c, '⏳ Запрос на бой отправлен противнику. Ожидаем решения...', app.back('attack'))


async def battle_decline(c, attacker_id, bot: Bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    invite = await get_invite(attacker_id, defender_id)
    if not invite:
        return await c.answer('Предложение уже недействительно.', show_alert=True)
    await delete_invite(attacker_id)
    try:
        await c.answer('Бой отменён.')
    except Exception:
        pass
    _, _, attacker_chat, attacker_msg, _, _, _, _ = invite
    try:
        await c.message.edit_text('🏳️ Бой отклонён.', parse_mode=None)
    except Exception:
        pass
    await edit_existing(bot, attacker_chat, attacker_msg, '🏳️ Противник отказался от боя.', app.back('attack'))


async def battle_accept(c, attacker_id, bot: Bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    invite = await reserve_invite(attacker_id, defender_id)
    if not invite:
        existing = await get_invite(attacker_id, defender_id)
        if existing and int(existing[7]) == 1:
            return await c.answer('Бой уже запущен.', show_alert=True)
        return await c.answer('Предложение уже недействительно.', show_alert=True)

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        await delete_invite(attacker_id)
        return await c.answer('Игрок не найден.', show_alert=True)

    _, _, attacker_chat, attacker_msg, defender_chat, defender_msg, _, _ = invite
    try:
        await c.answer()
    except Exception:
        pass

    async def frame(text):
        # The two edits are awaited together. Neither side can advance its
        # animation independently of the other side.
        await asyncio.gather(
            edit_existing(bot, attacker_chat, attacker_msg, text),
            edit_existing(bot, defender_chat, defender_msg, text),
            return_exceptions=True,
        )

    # One monotonic clock controls both players. The first frame is shown at
    # the same moment for both, then each next frame is scheduled against the
    # same absolute deadline. This avoids drift from Telegram API latency.
    start = asyncio.get_running_loop().time()
    for index, second in enumerate(range(15, 0, -1)):
        await frame(f'⚔️ БОЙ\n\n{BATTLE_LINES[index]}\n\n⏱ {second} сек.')
        target = start + (index + 1)
        delay = target - asyncio.get_running_loop().time()
        if delay > 0:
            await asyncio.sleep(delay)

    # No result is calculated or displayed before the last animation frame.
    a_after, d_after, winner, events, kills_a, kills_d = resolve(attacker, defender, with_kills=True)
    winner_id = attacker_id if winner == 'attacker' else defender_id
    loser_id = defender_id if winner == 'attacker' else attacker_id
    winner_arm = a_after if winner == 'attacker' else d_after
    loser_raw = d_after if winner == 'attacker' else a_after
    loser_before = defender if winner == 'attacker' else attacker
    loser_arm = {key: int(loser_raw[key]) * 80 // 100 for key in UNITS}
    winner_kills = kills_a if winner == 'attacker' else kills_d
    loser_kills = kills_d if winner == 'attacker' else kills_a

    reward = int(sum(int(winner_kills.get(k, 0)) * UNITS[k]['price'] for k in UNITS) * 0.05)
    loser_reward = int(sum((int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price'] for k in UNITS) * 0.02)

    db = await connect()
    try:
        sets = ','.join(f'{k}=?' for k in UNITS)
        kill_sets = ','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(
            f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',
            [winner_arm[k] for k in UNITS] + [now_iso(), winner_id],
        )
        await db.execute(
            f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',
            [loser_arm[k] for k in UNITS] + [now_iso(), loser_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [int(winner_kills.get(k, 0)) for k in UNITS] + [winner_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [int(loser_kills.get(k, 0)) for k in UNITS] + [loser_id],
        )
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (reward, winner_id))
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (loser_reward, loser_id))
        await db.commit()
    finally:
        await db.close()
    await delete_invite(attacker_id)

    winner_row = await user(winner_id)
    winner_name = '@' + winner_row['username'] if winner_row and winner_row['username'] else f'ID {winner_id}'
    win_text = (
        '🏆 WIN\n\n' f'Победитель: {winner_name}\n'
        f'💰 Награда: ${money(reward)}\n\n🎯 Уничтожено:\n{kills_text(winner_kills)}'
    )
    loss_text = (
        '💀 LOSS\n\n' f'Победитель: {winner_name}\n'
        '📉 Твоя армия: −20%\n' f'💵 Компенсация: ${money(loser_reward)}\n\n'
        f'🎯 Уничтожено:\n{kills_text(loser_kills)}'
    )

    # Both final messages are also updated together. The attacker therefore
    # cannot receive "you lost" before the defender has finished the battle.
    await asyncio.gather(
        edit_existing(bot, attacker_chat, attacker_msg, win_text if winner_id == attacker_id else loss_text, app.back()),
        edit_existing(bot, defender_chat, defender_msg, win_text if winner_id == defender_id else loss_text, app.back()),
        return_exceptions=True,
    )


async def _call_with_bot(handler, event, bot):
    """Call legacy handlers safely regardless of whether they name the bot
    argument `bot` or `tg_bot`.
    """
    params = inspect.signature(handler).parameters
    if 'tg_bot' in params:
        result = handler(event, tg_bot=bot)
    elif 'bot' in params:
        result = handler(event, bot=bot)
    else:
        result = handler(event)
    if inspect.isawaitable(result):
        return await result
    return result


async def callback(c, bot: Bot):
    data = c.data or ''
    if data == 'battle_confirm':
        return await battle_confirm(c, bot)
    if data.startswith('oam_accept:'):
        try:
            return await battle_accept(c, int(data.split(':', 1)[1]), bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)
    if data.startswith('oam_decline:'):
        try:
            return await battle_decline(c, int(data.split(':', 1)[1]), bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)
    if data.startswith('accept:') or data.startswith('decline:'):
        return await c.answer('Это старое приглашение. Создайте новый бой.', show_alert=True)
    return await _call_with_bot(run.callback, c, bot)


async def start_wrapper(message, bot: Bot):
    return await _call_with_bot(run.start_wrapper, message, bot)


async def text_handler(message, bot: Bot):
    return await _call_with_bot(run.text_handler, message, bot)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is empty')
    await init_db()
    await ensure_battle_table()
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

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(start_wrapper, CommandStart())
    dp.message.register(text_handler, F.text)
    dp.callback_query.register(callback, F.data)

    print('[OAM FIX] STARTED: fix.py')
    print('[OAM FIX] SQLite battle invites: ON')
    print('[OAM FIX] shared 15-second animation: ON')
    print('[OAM FIX] all kill counters: ON')
    print('[OAM FIX] tg_bot compatibility adapter: ON')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
