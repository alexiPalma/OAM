import run
import admin_runtime

_ORIGINAL_CALLBACK = run.callback
_ORIGINAL_TEXT_HANDLER = run.text_handler


def is_promo_callback(data):
    return (
        data == 'a_promos'
        or data == 'promo_create'
        or data.startswith('promo_type:')
        or data.startswith('promo_unit:')
        or data.startswith('promo_case:')
        or data == 'promo_list'
        or data == 'promo_delete'
        or data.startswith('promo_del:')
    )


async def callback(c, bot):
    data = c.data or ''
    if is_promo_callback(data):
        return await admin_runtime.callback(c, bot)
    return await _ORIGINAL_CALLBACK(c, bot)


async def text_handler(message, bot):
    text = (message.text or '').strip()
    parts = text.split()
    command = parts[0].split('@')[0].lower() if parts else ''
    state = getattr(run.app, 'STATE', {}).get(message.from_user.id)
    if command in ('/addpromo', '/createpromo', '/deletepromo'):
        return await admin_runtime.text_handler(message, bot)
    if state and str(state[0]).startswith('promo_'):
        return await admin_runtime.text_handler(message, bot)
    return await _ORIGINAL_TEXT_HANDLER(message, bot)


run.callback = callback
run.text_handler = text_handler
print('[OAM] PROMO UI BRIDGE: ON')
