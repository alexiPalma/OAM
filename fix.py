"""OAM FIX ENTRYPOINT.

This file is the ONLY entrypoint for the bot. Battle invitations and the
15-second battle animation live here and use unique callback prefixes so old
battle handlers in bot.py cannot steal the button press.
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

INVITE_TTL = timedelta(seconds=60)
INVITES = {}

BATTLE_LINES = [
    '⚔️ Идёт бой',
    '💥 Гремят взрывы',
    '🪖 Пехота зачищает позиции',
    '🔥 Раздаются выстрелы',
    '🌫 Над полем боя поднимается дым',
    '⚡ Ударная волна проходит по позиции',
    '🚙 БМП открыли огонь',
    '💥 Артиллерия работает',
    '🛡 Танки продвигаются вперёд',
    '🚁 Вертолёты атакуют',
    '✈️ Самолёты наносят удар',
    '🚀 Ракетный удар',
    '🛰 Последняя атака',
    '⏳ Последние секунды боя',
    '🏆 Бой завершён',
]


def now():
    return datetime.now(timezone.utc)


def money(value):
    return f'{int(value):,}'.replace(',', ' ')


def kills_text(kills):
    # Always print EVERY unit, including zero kills.
    return '\n'.join(
        f'{UNITS[key]["title"]}: {int(kills.get(key, 0))}'
        for key in UNITS
    )


async def edit_existing(bot, chat_id, message_id, text, markup=None):
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
        print(f'[OAM FIX] edit failed {chat_id}/{message_id}: {exc}')
        return False


def get_invite(attacker_id, defender_id):
    invite = INVITES.get(int(attacker_id))
    if not invite:
        return None
    if int(invite['defender_id']) != int(defender_id):
        return None
    if now() - invite['created_at'] > INVITE_TTL:
        INVITES.pop(int(attacker_id), None)
        return None
    return invite


async def battle_confirm(c, tg_bot):
    """Create the invitation. It is stored BEFORE Telegram send_message."""
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

    attacker_name = '@' + attacker['username'] if attacker['username'] else f'ID {attacker_id}'
    text = (
        '⚔️ WORLDWAR DYNASTY • НА ВАС НАПАЛИ\n\n'
        f'👤 Нападающий: {attacker_name}\n\n'
        f'{app.army_text(attacker)}\n\nПримите бой или откажитесь.'
    )
    keyboard = app.kb([
        [('⚔️ ПРИНЯТЬ БОЙ', f'oam_accept:{attacker_id}')],
        [('🏳️ ОТКАЗАТЬСЯ', f'oam_decline:{attacker_id}')],
    ])

    try:
        defender_message = await tg_bot.send_message(
            defender_id, text, reply_markup=keyboard
        )
    except Exception as exc:
        return await c.answer(
            f'Не удалось отправить приглашение: {exc}', show_alert=True
        )

    # The exact attacker message and defender message are kept together.
    INVITES[attacker_id] = {
        'attacker_id': attacker_id,
        'defender_id': defender_id,
        'created_at': now(),
        'attacker_chat_id': int(c.message.chat.id),
        'attacker_message_id': int(c.message.message_id),
        'defender_chat_id': int(defender_id),
        'defender_message_id': int(defender_message.message_id),
        'running': False,
    }

    await c.answer()
    return await app.safe(
        c,
        '⏳ Запрос на бой отправлен противнику. Ожидаем решения...',
        app.back('attack'),
    )


async def battle_decline(c, attacker_id, tg_bot):
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    invite = get_invite(attacker_id, defender_id)
    if not invite:
        return await c.answer('Предложение уже недействительно.', show_alert=True)

    INVITES.pop(attacker_id, None)
    try:
        await c.answer('Бой отменён.')
    except Exception:
        pass
    try:
        await c.message.edit_text('🏳️ Бой отклонён.', parse_mode=None)
    except Exception:
        pass
    await edit_existing(
        tg_bot,
        invite['attacker_chat_id'],
        invite['attacker_message_id'],
        '🏳️ Противник отказался от боя.',
        app.back('attack'),
    )


async def battle_accept(c, attacker_id, tg_bot):
    """Accept and run ONE shared 15-second clock for both messages."""
    attacker_id = int(attacker_id)
    defender_id = int(c.from_user.id)
    invite = get_invite(attacker_id, defender_id)
    if not invite:
        return await c.answer('Предложение уже недействительно.', show_alert=True)

    # Atomically reserve the invitation before doing any awaits. A second tap
    # can therefore never start a second battle.
    if invite['running']:
        return await c.answer('Бой уже запущен.', show_alert=True)
    invite['running'] = True

    attacker = await user(attacker_id)
    defender = await user(defender_id)
    if not attacker or not defender:
        INVITES.pop(attacker_id, None)
        return await c.answer('Игрок не найден.', show_alert=True)

    INVITES.pop(attacker_id, None)
    try:
        await c.answer()
    except Exception:
        pass

    attacker_chat = invite['attacker_chat_id']
    attacker_msg = invite['attacker_message_id']
    defender_chat = invite['defender_chat_id']
    defender_msg = invite['defender_message_id']

    async def frame(text):
        # Both edits are awaited together. No player gets a private 15-second
        # wait while the other is already watching the result.
        await asyncio.gather(
            edit_existing(tg_bot, attacker_chat, attacker_msg, text),
            edit_existing(tg_bot, defender_chat, defender_msg, text),
            return_exceptions=True,
        )

    await frame('⚔️ БОЙ\n\nБой начинается...\n\n⏱ 15 сек.')

    for second in range(15, 0, -1):
        line = BATTLE_LINES[15 - second]
        await frame(f'⚔️ БОЙ\n\n{line}\n\n⏱ {second} сек.')
        if second > 1:
            await asyncio.sleep(1)

    # Resolve ONLY after the shared animation has finished.
    a_after, d_after, winner, events, kills_a, kills_d = resolve(
        attacker, defender, with_kills=True
    )
    winner_id = attacker_id if winner == 'attacker' else defender_id
    loser_id = defender_id if winner == 'attacker' else attacker_id
    winner_arm = a_after if winner == 'attacker' else d_after
    loser_raw = d_after if winner == 'attacker' else a_after
    loser_before = defender if winner == 'attacker' else attacker
    loser_arm = {key: int(loser_raw[key]) * 80 // 100 for key in UNITS}
    winner_kills = kills_a if winner == 'attacker' else kills_d
    loser_kills = kills_d if winner == 'attacker' else kills_a

    reward = int(
        sum(int(winner_kills.get(k, 0)) * UNITS[k]['price'] for k in UNITS) * 0.05
    )
    loser_reward = int(
        sum(
            (int(loser_before[k]) - loser_arm[k]) * UNITS[k]['price']
            for k in UNITS
        ) * 0.02
    )

    db = await connect()
    try:
        sets = ','.join(f'{k}=?' for k in UNITS)
        kill_sets = ','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(
            f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',
            [winner_arm[k] for k in UNITS] + [now().isoformat(), winner_id],
        )
        await db.execute(
            f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',
            [loser_arm[k] for k in UNITS] + [now().isoformat(), loser_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [int(winner_kills.get(k, 0)) for k in UNITS] + [winner_id],
        )
        await db.execute(
            f'UPDATE users SET {kill_sets} WHERE user_id=?',
            [int(loser_kills.get(k, 0)) for k in UNITS] + [loser_id],
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
        '🏆 WIN\n\n'
        f'Победитель: {winner_name}\n'
        f'💰 Награда: ${money(reward)}\n\n'
        f'🎯 Уничтожено:\n{kills_text(winner_kills)}'
    )
    loss_text = (
        '💀 LOSS\n\n'
        f'Победитель: {winner_name}\n'
        '📉 Твоя армия: −20%\n'
        f'💵 Компенсация: ${money(loser_reward)}\n\n'
        f'🎯 Уничтожено:\n{kills_text(loser_kills)}'
    )

    # Both players receive the result only now, after the exact same animation.
    await asyncio.gather(
        edit_existing(
            tg_bot,
            attacker_chat,
            attacker_msg,
            win_text if winner_id == attacker_id else loss_text,
            app.back(),
        ),
        edit_existing(
            tg_bot,
            defender_chat,
            defender_msg,
            win_text if winner_id == defender_id else loss_text,
            app.back(),
        ),
        return_exceptions=True,
    )


async def callback(c, tg_bot):
    """Single callback router. Battle callbacks are intercepted first."""
    data = c.data or ''

    if data == 'battle_confirm':
        return await battle_confirm(c, tg_bot)
    if data.startswith('oam_accept:'):
        try:
            return await battle_accept(c, int(data.split(':', 1)[1]), tg_bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)
    if data.startswith('oam_decline:'):
        try:
            return await battle_decline(c, int(data.split(':', 1)[1]), tg_bot)
        except (ValueError, TypeError):
            return await c.answer('Некорректное приглашение.', show_alert=True)

    # Legacy battle buttons cannot start the old battle code anymore.
    if data.startswith('accept:') or data.startswith('decline:'):
        return await c.answer(
            'Это старое приглашение. Создайте новый бой.', show_alert=True
        )

    return await run.callback(c, tg_bot)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is empty')

    await init_db()
    await init_settings(ADMIN_ID)

    db = await connect()
    try:
        await db.execute(
            'INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (ADMIN_ID,)
        )
        if OWNER_ID2:
            await db.execute(
                'INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (OWNER_ID2,)
            )
        await db.commit()
    finally:
        await db.close()

    await achievements.init_achievements()
    try:
        achievements.install_sync()
    except Exception as exc:
        print(f'[OAM FIX] achievements hook skipped: {exc}')

    tg_bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(run.start_wrapper, CommandStart())
    dp.message.register(run.text_handler, F.text)
    dp.callback_query.register(callback, F.data)

    print('[OAM FIX] SINGLE ENTRYPOINT: fix.py')
    print('[OAM FIX] battle callbacks: oam_accept / oam_decline')
    print('[OAM FIX] one shared 15-second animation for both players')
    print('[OAM FIX] result appears only after the final frame')
    print('[OAM FIX] all 9 unit kill counters are always displayed')

    try:
        await dp.start_polling(tg_bot)
    finally:
        await tg_bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
