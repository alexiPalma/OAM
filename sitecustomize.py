"""Small startup compatibility fixes for the WorldWarDynasty bot.

Loaded automatically by Python's site module before run.py. This keeps the
main feature files untouched while normalising legacy message templates and
fixing the leaderboard/farm display.
"""

try:
    import bot as _app
    from db import top_users, user
    from config import FARMS

    # Legacy admin-edited templates sometimes contain the two literal
    # characters ``\\n`` instead of an actual newline. Normalise them before
    # formatting so Telegram renders real line breaks.
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
        text = await _app.tpl(
            'top',
            f'🏆 {_app.BRAND} • ТОП ВОЯК\n\n{listing}',
            top=listing,
            position='—',
        )
        return await _app.safe(c, text, _app.back())

    _app.top = _fixed_top

    async def _fixed_farm(c):
        row = await user(c.from_user.id)
        level = int(row['farm_level'])
        farm_data = FARMS[level]
        status = '🟢 АКТИВНА' if level > 0 else '⚪ НЕ РАЗВЁРНУТА'
        tax = _app.money(row['tax'])
        text = await _app.tpl(
            'farm',
            f'🏭 {_app.BRAND} • ФЕРМА\n\n'
            f'Уровень: {level}/10\n'
            f'Производство: ${_app.money(farm_data["income"])}/час\n'
            f'💸 Накоплено налога: ${tax}\n'
            f'Ставка налога: 25%\n'
            f'Статус: {status}',
            level=level,
            income=_app.money(farm_data['income']),
            tax=tax,
            status=status,
        )
        # Preserve custom templates, but guarantee that the accumulated tax is
        # visible even when an older template omitted the tax placeholder.
        if 'Накоплено налога' not in text and 'Налог:' not in text:
            text += f'\n\n💸 Накоплено налога: ${tax}'
        elif 'Налог:' in text and 'Накоплено налога' not in text:
            text = text.replace('Налог:', '💸 Накоплено налога:', 1)
        return await _app.safe(
            c,
            text,
            _app.kb([
                [('💰 Получить', 'payout'), ('⬆️ Улучшить', 'upgrade')],
                [('💸 Оплатить налог', 'paytax')],
                [('⬅️ Назад', 'home')],
            ]),
        )

    _app.farm = _fixed_farm

    # run.py has its own home keyboard, so add the important Achievements entry
    # there as well without replacing the existing menu.
    import run as _run
    _old_home_kb = _run.home_kb

    def _home_with_achievements(is_admin_user=False):
        markup = _old_home_kb(is_admin_user)
        rows = [list(row) for row in markup.inline_keyboard]
        if not any(button.callback_data == 'achievements' for row in rows for button in row):
            insert_at = len(rows) - (1 if is_admin_user else 0)
            rows.insert(max(0, insert_at), [_app.InlineKeyboardButton(text='🏆 Ачивки', callback_data='achievements')])
        return _app.InlineKeyboardMarkup(inline_keyboard=rows)

    _run.home_kb = _home_with_achievements
except Exception:
    # Never prevent the bot from starting because of this compatibility layer.
    pass
