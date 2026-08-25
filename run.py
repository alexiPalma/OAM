"""WorldWarDynasty application entrypoint.

This is the real launcher used by both Windows and Pterodactyl.
It keeps the existing bot feature set in bot.py and adds the bridge for
achievements, quests, earn tasks, URL buttons, and equipment promo codes.
"""
import asyncio
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import achievements
import bot as app
from config import ADMIN_ID, BOT_TOKEN, OWNER_ID2, OWNER_IDS, UNITS
from db import connect, init_db, is_admin, user
from settings import init_settings


def home_kb(is_admin_user=False):
    rows = [
        [('🏭 Ферма', 'farm'), ('🎖 Армия', 'army')],
        [('🛒 Арсенал', 'shop'), ('⚔️ Атака', 'attack')],
        [('💰 Заработать', 'earn'), ('📋 Задания', 'tasks')],
        [('🏆 Ачивки', 'achievements'), ('🎁 Бонус', 'bonus')],
        [('🎟 Промокод', 'promo'), ('📦 Кейсы', 'cases')],
        [('👤 Профиль', 'profile'), ('🏆 Топ вояк', 'top')],
        [('💳 Донат', 'donate'), ('📕 Правила', 'rules')],
        [('ℹ️ Помощь', 'help')],
    ]
    if is_admin_user:
        rows.append([('⚙️ Админ-панель', 'admin')])
    return app.kb(rows)


def earn_kb(tasks, claimed):
    """Build the earn keyboard correctly: task links are URL buttons, not callbacks."""
    labels = {
        'boost': '🚀 Буст канала / группы',
        'channel': '📢 Подписка на канал',
        'group': '👥 Вступление в группу',
    }
    rows = []
    for task in tasks:
        label = labels.get(task['kind'], task['kind'])
        if task['id'] in claimed:
            rows.append([InlineKeyboardButton(
                text=f'☑️ {label} · награда получена',
                callback_data='earn_done',
            )])
            continue
        url = str(task['url']).strip()
        rows.append([InlineKeyboardButton(
            text=f'{label} · +${app.money(task["reward"])}',
            url=url,
        )])
        rows.append([InlineKeyboardButton(
            text='✅ Проверить выполнение',
            callback_data=f'earn_check:{task["kind"]}:{task["id"]}',
        )])
    rows.append([InlineKeyboardButton(text='📋 Задания', callback_data='tasks')])
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def admin_ok(uid: int) -> bool:
    if uid in OWNER_IDS or (OWNER_ID2 and uid == OWNER_ID2):
        return True
    try:
        return bool(await is_admin(uid, ADMIN_ID))
    except Exception:
        return False


async def send_home(message):
    u = await user(message.from_user.id)
    if not u:
        await app.ensure_user(message.from_user.id, message.from_user.username)
        u = await user(message.from_user.id)
    text = (
        f'⚔️ {app.BRAND}\n\n'
        f'💵 Баланс: ${app.money(u["balance"])}\n'
        f'🏭 Ферма: {u["farm_level"]}/10\n\n'
        '🛰 Центр управления войсками:'
    )
    return await message.answer(text, reply_markup=home_kb(await admin_ok(message.from_user.id)))


async def home_callback(c):
    u = await user(c.from_user.id)
    if not u:
        await app.ensure_user(c.from_user.id, c.from_user.username)
        u = await user(c.from_user.id)
    text = (
        f'⚔️ {app.BRAND}\n\n'
        f'💵 Баланс: ${app.money(u["balance"])}\n'
        f'🏭 Ферма: {u["farm_level"]}/10\n\n'
        '🛰 Центр управления войсками:'
    )
    return await app.safe(c, text, home_kb(await admin_ok(c.from_user.id)))


async def tasks(c):
    await app.ensure_user(c.from_user.id, c.from_user.username)
    u = await user(c.from_user.id)
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT quest_id FROM quest_claims WHERE user_id=?',
            (c.from_user.id,),
        )
        claimed = {r['quest_id'] for r in await cur.fetchall()}
    finally:
        await db.close()

    rows = []
    for qid, title, reward in getattr(app, 'FIXED_QUESTS', []):
        if qid in claimed:
            rows.append([(f'☑️ {title} — получено', f'task_locked:{qid}')])
            continue
        done = (
            (qid == 'earn_any' and await app.earn_any_done(c.from_user.id))
            or (qid == 'buy_soldier_10' and int(u['soldier']) >= 10)
            or (qid == 'fight_once' and int(u['attacks_won']) + int(u['attacks_lost']) >= 1)
            or (qid == 'buy_interceptor_50' and int(u['interceptor']) >= 50)
            or (qid == 'buy_bmp' and int(u['bmp']) >= 1)
        )
        rows.append([((('✅' if done else '🔒') + f' {title} · {reward}'), f'quest:{qid}')])
    rows += [[('💰 К заработку', 'earn')], [('⬅️ Назад', 'home')]]
    return await app.safe(
        c,
        f'📋 {app.BRAND} • ЗАДАНИЯ\n\nВыполняйте постоянные задания и забирайте награды.',
        app.kb(rows),
    )


async def tasks_message(message):
    await app.ensure_user(message.from_user.id, message.from_user.username)
    u = await user(message.from_user.id)
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT quest_id FROM quest_claims WHERE user_id=?',
            (message.from_user.id,),
        )
        claimed = {r['quest_id'] for r in await cur.fetchall()}
    finally:
        await db.close()

    rows = []
    for qid, title, reward in getattr(app, 'FIXED_QUESTS', []):
        if qid in claimed:
            rows.append([(f'☑️ {title} — получено', f'task_locked:{qid}')])
            continue
        done = (
            (qid == 'earn_any' and await app.earn_any_done(message.from_user.id))
            or (qid == 'buy_soldier_10' and int(u['soldier']) >= 10)
            or (qid == 'fight_once' and int(u['attacks_won']) + int(u['attacks_lost']) >= 1)
            or (qid == 'buy_interceptor_50' and int(u['interceptor']) >= 50)
            or (qid == 'buy_bmp' and int(u['bmp']) >= 1)
        )
        rows.append([((('✅' if done else '🔒') + f' {title} · {reward}'), f'quest:{qid}')])
    rows += [[('💰 К заработку', 'earn')], [('⬅️ Назад', 'home')]]
    return await message.answer(
        f'📋 {app.BRAND} • ЗАДАНИЯ\n\nВыполняйте постоянные задания и забирайте награды.',
        reply_markup=app.kb(rows),
    )


async def load_earn_tasks(uid):
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id'
        )
        tasks = await cur.fetchall()
        cur = await db.execute(
            'SELECT task_id FROM earn_claims WHERE user_id=?',
            (uid,),
        )
        claimed = {r['task_id'] for r in await cur.fetchall()}
        return tasks, claimed
    finally:
        await db.close()


async def earn(c):
    tasks, claimed = await load_earn_tasks(c.from_user.id)
    body = (
        'Пока нет активных предложений.\n\n'
        'Администратор может добавить их через админ-панель.'
        if not tasks
        else 'Нажмите на ссылку, выполните действие, затем нажмите «Проверить выполнение».'
    )
    return await app.safe(
        c,
        f'💰 {app.BRAND} • ЗАРАБОТАТЬ\n\n{body}',
        earn_kb(tasks, claimed),
    )


async def earn_message(message):
    tasks, claimed = await load_earn_tasks(message.from_user.id)
    body = (
        'Пока нет активных предложений.'
        if not tasks
        else 'Нажмите на ссылку, выполните действие, затем нажмите «Проверить выполнение».'
    )
    return await message.answer(
        f'💰 {app.BRAND} • ЗАРАБОТАТЬ\n\n{body}',
        reply_markup=earn_kb(tasks, claimed),
    )


def telegram_chat_from_url(raw_url: str):
    url = str(raw_url or '').strip()
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return None
    host = parsed.netloc.lower().split(':', 1)[0]
    if host not in ('t.me', 'www.t.me', 'telegram.me', 'www.telegram.me'):
        return None
    parts = [p for p in parsed.path.split('/') if p]
    if len(parts) != 1:
        return None
    username = parts[0]
    if username.startswith(('+', 'joinchat')):
        return None
    if not username.replace('_', '').isalnum():
        return None
    return '@' + username


async def check_dynamic_earn(c, kind, task_id, tg_bot: Bot):
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT * FROM earn_tasks WHERE id=? AND kind=? AND active=1',
            (task_id, kind),
        )
        task = await cur.fetchone()
        if not task:
            return await c.answer('Задание не найдено.', show_alert=True)
        cur = await db.execute(
            'SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?',
            (c.from_user.id, task_id),
        )
        if await cur.fetchone():
            return await c.answer('Награда уже получена.', show_alert=True)
    finally:
        await db.close()

    chat = telegram_chat_from_url(task['url'])
    if not chat:
        return await c.answer(
            '❌ Для проверки нужна публичная ссылка вида https://t.me/channel',
            show_alert=True,
        )

    try:
        if kind == 'boost':
            method = getattr(tg_bot, 'get_user_chat_boosts', None)
            if method is None:
                return await c.answer(
                    '❌ В установленной версии aiogram нет проверки бустов.',
                    show_alert=True,
                )
            result = await method(chat_id=chat, user_id=c.from_user.id)
            ok = bool(getattr(result, 'boosts', None))
        else:
            member = await tg_bot.get_chat_member(chat, c.from_user.id)
            ok = member.status not in ('left', 'kicked')
    except Exception:
        return await c.answer(
            '❌ Не удалось проверить участие. Убедись, что бот добавлен администратором в канал/группу.',
            show_alert=True,
        )

    if not ok:
        return await c.answer('❌ Ты ещё не выполнил условие.', show_alert=True)

    db = await connect()
    try:
        cur = await db.execute(
            'SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?',
            (c.from_user.id, task_id),
        )
        if await cur.fetchone():
            return await c.answer('Награда уже получена.', show_alert=True)
        await db.execute(
            'UPDATE users SET balance=balance+? WHERE user_id=?',
            (task['reward'], c.from_user.id),
        )
        await db.execute(
            'INSERT INTO earn_claims(user_id,task_id) VALUES(?,?)',
            (c.from_user.id, task_id),
        )
        await db.commit()
    finally:
        await db.close()

    return await c.answer(
        f'🎉 Условие выполнено! +${app.money(task["reward"])}',
        show_alert=True,
    )


async def use_promo_extended(message, code):
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT * FROM promos WHERE lower(code)=lower(?)',
            (code.strip(),),
        )
        promo = await cur.fetchone()
        if not promo:
            return await message.answer('❌ Промокод не найден.')
        if int(promo['uses']) >= int(promo['max_uses']):
            return await message.answer('❌ Промокод больше недоступен.')
        cur = await db.execute(
            'SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',
            (promo['code'], message.from_user.id),
        )
        if await cur.fetchone():
            return await message.answer('❌ Вы уже использовали этот промокод.')

        reward_type = str(promo['reward_type'] or 'money')
        amount = int(promo['reward_amount'] or promo['amount'] or 0)
        if reward_type == 'money':
            await db.execute(
                'UPDATE users SET balance=balance+? WHERE user_id=?',
                (amount, message.from_user.id),
            )
            reward_text = f'💵 +${app.money(amount)}'
        elif reward_type.startswith('unit:'):
            unit = reward_type.split(':', 1)[1]
            if unit not in UNITS or amount <= 0:
                return await message.answer('❌ Промокод содержит некорректную технику.')
            await db.execute(
                f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',
                (amount, message.from_user.id),
            )
            reward_text = f'{UNITS[unit]["title"]} × {amount}'
        else:
            return await message.answer('❌ Неизвестный тип награды промокода.')

        await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?', (promo['code'],))
        await db.execute(
            'INSERT INTO promo_uses(code,user_id) VALUES(?,?)',
            (promo['code'], message.from_user.id),
        )
        await db.commit()
    finally:
        await db.close()
    return await message.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward_text}')


async def add_promo(message, parts):
    if not await admin_ok(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')

    reward_type = 'money'
    if len(parts) == 3:
        code, amount_s, max_s = parts
    elif len(parts) == 4 and parts[1].lower() == 'money':
        code, _, amount_s, max_s = parts
    elif len(parts) == 5 and parts[1].lower() in ('unit', 'tech', 'equipment'):
        code, _, unit, amount_s, max_s = parts
        unit = unit.lower()
        if unit not in UNITS:
            return await message.answer('❌ Неизвестная техника: ' + ', '.join(UNITS))
        reward_type = 'unit:' + unit
    else:
        return await message.answer(
            '❌ Формат:\n'
            '/addpromo КОД СУММА ЛИМИТ\n'
            '/addpromo КОД money СУММА ЛИМИТ\n'
            '/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n\n'
            'Пример:\n/addpromo TANK2026 unit tank 2 100'
        )

    try:
        amount, max_uses = int(amount_s), int(max_s)
    except ValueError:
        return await message.answer('❌ Сумма, количество и лимит должны быть числами.')
    if amount <= 0 or max_uses <= 0:
        return await message.answer('❌ Сумма/количество и лимит должны быть больше нуля.')

    db = await connect()
    try:
        money_amount = amount if reward_type == 'money' else 0
        await db.execute(
            '''INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount)
               VALUES(?,?,0,?,?,?)
               ON CONFLICT(code) DO UPDATE SET
                 amount=excluded.amount,
                 max_uses=excluded.max_uses,
                 reward_type=excluded.reward_type,
                 reward_amount=excluded.reward_amount''',
            (code, money_amount, max_uses, reward_type, amount),
        )
        await db.commit()
    finally:
        await db.close()

    reward_text = (
        f'${app.money(amount)}'
        if reward_type == 'money'
        else f'{UNITS[reward_type.split(":", 1)[1]]["title"]} × {amount}'
    )
    return await message.answer(
        f'✅ Промокод создан/обновлён.\n\n'
        f'🎟 {code}\n🎁 {reward_text}\n👥 Лимит: {max_uses}'
    )


async def take_unit(message, parts):
    if not await admin_ok(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')
    if len(parts) != 3:
        return await message.answer('❌ Формат: /takeunit @username тип количество')
    target = await app.find_user(parts[0])
    unit = parts[1].lower()
    try:
        amount = int(parts[2])
    except ValueError:
        amount = 0
    if target is None or unit not in UNITS or amount <= 0:
        return await message.answer('❌ Неверные данные.')
    db = await connect()
    try:
        cur = await db.execute(
            f'UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?',
            (amount, target['user_id']),
        )
        await db.commit()
    finally:
        await db.close()
    return await message.answer('✅ Техника списана.' if cur.rowcount else '❌ Не удалось списать технику.')


async def take_cash(message, parts):
    if not await admin_ok(message.from_user.id):
        return await message.answer('⛔ Нет доступа.')
    if len(parts) != 2:
        return await message.answer('❌ Формат: /takecash @username сумма')
    target = await app.find_user(parts[0])
    try:
        amount = int(parts[1])
    except ValueError:
        amount = 0
    if target is None or amount <= 0:
        return await message.answer('❌ Неверные данные.')
    db = await connect()
    try:
        cur = await db.execute(
            'UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?',
            (amount, target['user_id']),
        )
        await db.commit()
    finally:
        await db.close()
    return await message.answer('✅ Списано.' if cur.rowcount else '❌ Не удалось списать баланс.')


async def callback(c, bot: Bot):
    data = c.data or ''
    if data == 'home':
        return await home_callback(c)
    if data == 'tasks':
        return await tasks(c)
    if data.startswith('task_locked:'):
        return await c.answer('Это задание уже получено.', show_alert=True)
    if data == 'earn':
        return await earn(c)
    if data.startswith('earn_check:'):
        try:
            _, kind, tid = data.split(':', 2)
            return await check_dynamic_earn(c, kind, int(tid), bot)
        except (ValueError, TypeError):
            return await c.answer('❌ Некорректное задание.', show_alert=True)
    if data == 'earn_done':
        return await c.answer('Награда уже получена.', show_alert=True)
    if data == 'achievements':
        return await achievements.menu(c)
    if data.startswith('ach:'):
        return await achievements.detail(c, data.split(':', 1)[1])
    if data.startswith('ach_claim:'):
        return await achievements.claim(c, data.split(':', 1)[1])
    if data in ('a_promos', 'a_give', 'a_takeunit'):
        if data == 'a_promos':
            return await app.safe(
                c,
                '🎟 ПРОМОКОДЫ\n\n'
                '/addpromo КОД СУММА ЛИМИТ\n'
                '/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ',
                app.back('admin'),
            )
        if data == 'a_give':
            return await app.safe(c, '🎖 ВЫДАТЬ\n\n/givecash @user сумма\n/givepehot @user ID количество', app.back('admin'))
        return await app.safe(c, '➖ СПИСАТЬ\n\n/takecash @user сумма\n/takeunit @user тип количество', app.back('admin'))
    return await app.callback(c, bot)


async def text_handler(message, bot: Bot):
    text = (message.text or '').strip()
    parts = text.split()
    command = parts[0].split('@')[0].lower() if parts else ''
    low = text.lower()

    if low in ('адм', 'админ', '/адм', '/админ', '/admin', '/adm'):
        if not await admin_ok(message.from_user.id):
            return await message.answer('⛔ Нет доступа.')
        return await message.answer(
            f'⚙️ {app.BRAND} • АДМИН-ПАНЕЛЬ\n\nВыберите раздел:',
            reply_markup=app.admin_kb(),
        )
    if command == '/takeunit':
        return await take_unit(message, parts[1:])
    if command == '/takecash':
        return await take_cash(message, parts[1:])
    if command == '/addpromo':
        return await add_promo(message, parts[1:])
    if low in ('задания', 'задание', '/задания', '/задание'):
        return await tasks_message(message)
    if low in ('заработать', '/заработать'):
        return await earn_message(message)
    if command in ('/promo', '/промо', '/промокод') and len(parts) >= 2:
        return await use_promo_extended(message, parts[1])
    if low in ('промо', 'промокод', '/промо', '/промокод', '/promo'):
        return await message.answer('🎟 Введите промокод:')
    if not text.startswith('/') and (low.startswith('промокод ') or low.startswith('промо ')):
        return await use_promo_extended(message, parts[1])
    return await app.text_handler(message, bot)


async def start_wrapper(message):
    return await send_home(message)


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
    achievements.install_sync()

    tg = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(start_wrapper, CommandStart())
    dp.message.register(text_handler, F.text)
    dp.callback_query.register(callback, F.data)

    print(f'{app.BRAND} started')
    await dp.start_polling(tg)


if __name__ == '__main__':
    asyncio.run(main())
