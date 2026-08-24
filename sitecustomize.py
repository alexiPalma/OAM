"""Startup compatibility fixes for WorldWarDynasty."""

try:
    import re
    import bot as _app
    from db import top_users, user, connect
    from config import FARMS
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    async def _tpl(key, default, **kw):
        raw = await _app.setting('msg_' + key, default)
        if isinstance(raw, str):
            raw = raw.replace('\\r\\n', '\n').replace('\\n', '\n')
        try:
            return _app.clean(raw).format(**kw)
        except Exception:
            fallback = default
            if isinstance(fallback, str):
                fallback = fallback.replace('\\r\\n', '\n').replace('\\n', '\n')
            try:
                return _app.clean(fallback).format(**kw)
            except Exception:
                return _app.clean(fallback)

    _app.tpl = _tpl

    async def _fixed_top(c):
        rows = await top_users(50)
        out = []
        for i, row in enumerate(rows, 1):
            medal = ['🥇', '🥈', '🥉'][i - 1] if i <= 3 else '🎖️'
            name = '@' + row['username'] if row['username'] else f'ID {row["user_id"]}'
            out.append(f'{medal} {i}. {_app.esc(name)} — 🎖 {int(row["army_total"]):,}'.replace(',', ' '))
        listing = '\n'.join(out) or 'Пока игроков нет.'
        text = await _app.tpl('top', f'🏆 {_app.BRAND} • ТОП ВОЯК\n\n{listing}', top=listing, position='—')
        return await _app.safe(c, text, _app.back())

    _app.top = _fixed_top

    async def _fixed_farm(c):
        row = await user(c.from_user.id)
        level = int(row['farm_level'])
        farm_data = FARMS[level]
        tax = _app.money(row['tax'])
        status = '🟢 АКТИВНА' if level > 0 else '⚪ НЕ РАЗВЁРНУТА'
        text = await _app.tpl(
            'farm',
            f'🏭 {_app.BRAND} • ФЕРМА\n\n'
            f'Уровень: {level}/10\n'
            f'Производство: ${_app.money(farm_data["income"])}/час\n'
            f'💸 Накоплено налога: ${tax}\n'
            f'Ставка налога: 25%\n'
            f'Статус: {status}',
            level=level, income=_app.money(farm_data['income']), tax=tax, status=status,
        )
        if 'Накоплено налога' not in text and 'Налог:' not in text:
            text += f'\n\n💸 Накоплено налога: ${tax}'
        elif 'Налог:' in text and 'Накоплено налога' not in text:
            text = text.replace('Налог:', '💸 Накоплено налога:', 1)
        return await _app.safe(c, text, _app.kb([
            [('💰 Получить', 'payout'), ('⬆️ Улучшить', 'upgrade')],
            [('💸 Оплатить налог', 'paytax')],
            [('⬅️ Назад', 'home')],
        ]))

    _app.farm = _fixed_farm

    async def _channel_check(c, kind, task_id, tg_bot):
        db = await connect()
        try:
            cur = await db.execute('SELECT * FROM earn_tasks WHERE id=? AND kind=? AND active=1', (task_id, kind))
            task = await cur.fetchone()
            if not task:
                return await c.answer('❌ Задание не найдено.', show_alert=True)
            cur = await db.execute('SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?', (c.from_user.id, task_id))
            if await cur.fetchone():
                return await c.answer('✅ Награда уже получена.', show_alert=True)
        finally:
            await db.close()

        match = re.match(r'^https?://t\.me/([A-Za-z0-9_]+)(?:/)?(?:\?.*)?$', task['url'].strip())
        if not match:
            return await c.answer('❌ Для проверки нужна публичная ссылка вида https://t.me/channel', show_alert=True)
        chat = '@' + match.group(1)
        try:
            member = await tg_bot.get_chat_member(chat, c.from_user.id)
        except Exception:
            return await c.answer('❌ Бот не может проверить канал. Выдай боту права администратора в этом канале.', show_alert=True)

        if member.status in ('left', 'kicked'):
            return await c.answer('❌ Ты ещё не подписался на канал.', show_alert=True)

        db = await connect()
        try:
            cur = await db.execute('SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?', (c.from_user.id, task_id))
            if await cur.fetchone():
                return await c.answer('✅ Награда уже получена.', show_alert=True)
            await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (task['reward'], c.from_user.id))
            await db.execute('INSERT INTO earn_claims(user_id,task_id) VALUES(?,?)', (c.from_user.id, task_id))
            await db.commit()
        finally:
            await db.close()
        return await c.answer(f'🎉 Подписка подтверждена! +${_app.money(task["reward"])}', show_alert=True)

    _old_callback = _app.callback

    async def _callback(c, bot):
        data = c.data or ''
        if data.startswith('channel_check:'):
            _, kind, tid = data.split(':', 2)
            return await _channel_check(c, kind, int(tid), bot)
        if data.startswith('earn_check:'):
            _, kind, tid = data.split(':', 2)
            if kind == 'channel':
                return await _channel_check(c, kind, int(tid), bot)
        return await _old_callback(c, bot)

    _app.callback = _callback

    # When bot.py itself renders the dynamic earn screen, use an explicit
    # Subscribe -> Check flow. run.py has its own screen but uses the same
    # callback handler above.
    async def _fixed_earn(c):
        db = await connect()
        cur = await db.execute('SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id')
        tasks = await cur.fetchall()
        cur = await db.execute('SELECT task_id FROM earn_claims WHERE user_id=?', (c.from_user.id,))
        claimed = {r['task_id'] for r in await cur.fetchall()}
        await db.close()
        labels = {'boost': '🚀 Буст канала / группы', 'channel': '📢 Подписка на канал', 'group': '👥 Вступление в группу'}
        rows = []
        for task in tasks:
            label = labels.get(task['kind'], task['kind'])
            if task['id'] in claimed:
                rows.append([('☑️ ' + label + ' — награда получена', 'earn_done')])
                continue
            action_text = '📢 Подписаться на канал' if task['kind'] == 'channel' else label
            check_data = f'channel_check:{task["kind"]}:{task["id"]}' if task['kind'] == 'channel' else f'earn_check:{task["kind"]}:{task["id"]}'
            rows.append([(action_text + f' · +${_app.money(task["reward"])}', task['url'])])
            rows.append([('🔎 Проверить подписку' if task['kind'] == 'channel' else '✅ Проверить выполнение', check_data)])
        rows += [[('📋 Задания', 'tasks')], [('⬅️ Назад', 'home')]]
        body = 'Пока нет активных предложений.' if not tasks else 'Нажми «Подписаться», подпишись на канал, затем нажми «Проверить подписку». '
        return await _app.safe(c, f'💰 {_app.BRAND} • ЗАРАБОТАТЬ\n\n{body}', _app.kb(rows))

    _app.earn = _fixed_earn
except Exception:
    pass
