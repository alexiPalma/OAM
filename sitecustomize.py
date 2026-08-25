"""Permanent startup fixes for WorldWarDynasty."""

try:
    import sys
    import bot as _app
    from db import top_users, user
    from config import FARMS
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    def _fixed_kb(rows):
        keyboard = []
        for row in rows:
            buttons = []
            for text, value in row:
                value = str(value)
                if value.startswith(("https://", "http://", "tg://")):
                    buttons.append(InlineKeyboardButton(text=str(text), url=value))
                else:
                    buttons.append(InlineKeyboardButton(text=str(text), callback_data=value))
            keyboard.append(buttons)
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    _app.kb = _fixed_kb

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
        text = await _app.tpl('farm', f'🏭 {_app.BRAND} • ФЕРМА\n\nУровень: {level}/10\nПроизводство: ${_app.money(farm_data["income"])}/час\n💸 Накоплено налога: ${tax}\nСтавка налога: 25%\nСтатус: {status}', level=level, income=_app.money(farm_data['income']), tax=tax, status=status)
        if 'Накоплено налога' not in text and 'Налог:' not in text:
            text += f'\n\n💸 Накоплено налога: ${tax}'
        elif 'Налог:' in text and 'Накоплено налога' not in text:
            text = text.replace('Налог:', '💸 Накоплено налога:', 1)
        return await _app.safe(c, text, _app.kb([[('💰 Получить', 'payout'), ('⬆️ Улучшить', 'upgrade')], [('💸 Оплатить налог', 'paytax')], [('⬅️ Назад', 'home')]]))

    _app.farm = _fixed_farm

    def _patch_main_home(frame):
        main_globals = frame.f_globals
        old_home = main_globals.get('home_kb')
        if old_home is None or getattr(old_home, '_achievements_menu_patch', False):
            return False
        def _home_with_achievements(is_admin_user=False):
            markup = old_home(is_admin_user)
            rows = [list(row) for row in markup.inline_keyboard]
            if not any(button.callback_data == 'achievements' for row in rows for button in row):
                insert_at = len(rows) - (1 if is_admin_user else 0)
                rows.insert(max(0, insert_at), [InlineKeyboardButton(text='🏆 Ачивки', callback_data='achievements')])
            return InlineKeyboardMarkup(inline_keyboard=rows)
        _home_with_achievements._achievements_menu_patch = True
        main_globals['home_kb'] = _home_with_achievements
        return True

    def _trace(frame, event, arg):
        if event in ('line', 'return') and frame.f_globals.get('__name__') == '__main__':
            filename = str(frame.f_globals.get('__file__', ''))
            if filename.endswith('run.py') and _patch_main_home(frame):
                sys.settrace(None)
                return None
        return _trace
    sys.settrace(_trace)
except Exception:
    pass
