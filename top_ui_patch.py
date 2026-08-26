"""Runtime UI patch: fix Top Warriors line breaks and ranking layout."""

from bot import BRAND, back, esc, safe, top_users, setting


def _normalize_newlines(value):
    # Admin-edited templates may contain the two literal characters \\ and n.
    # Telegram must receive a real line break instead.
    return str(value or '').replace('\\r\\n', '\n').replace('\\n', '\n').replace('\\r', '\n')


async def patched_tpl(key, default, **kw):
    raw = await setting('msg_' + key, default)
    raw = _normalize_newlines(raw)
    try:
        return _normalize_newlines(raw.format(**kw))
    except Exception:
        return _normalize_newlines(default)


async def patched_top(c):
    rows = await top_users(50)
    out = []
    for i, r in enumerate(rows, 1):
        medal = ['🥇', '🥈', '🥉'][i - 1] if i <= 3 else '🎖️'
        name = '@' + r['username'] if r['username'] else f'ID {r["user_id"]}'
        out.append(f'{medal} {i}. {esc(name)} — 🎖 {int(r["army_total"]):,}'.replace(',', ' '))

    body = '\n'.join(out) if out else 'Пока игроков нет.'
    default = f'🏆 {BRAND} • ТОП ВОЯК\n\n{body}'
    text = await patched_tpl('top', default, top=body, position='—')
    return await safe(c, text, back())


# Monkey-patch the functions actually called by bot.callback.
import bot as _app
_app.tpl = patched_tpl
_app.top = patched_top
