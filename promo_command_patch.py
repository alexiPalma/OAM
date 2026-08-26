"""Fix two-step promo entry.

The intended flow is: user sends `промо` (or `/промо`), bot asks for the
code, then the next ordinary message is treated as the promo code.
Direct `промо CODE` / `/промо CODE` remains supported too.
"""

import run

PROMO_WAITING = set()

_original_text_handler = run.text_handler


async def patched_text_handler(message, bot):
    text = (message.text or '').strip()
    low = text.lower()
    parts = text.split()
    command = parts[0].split('@')[0].lower() if parts else ''
    uid = int(message.from_user.id)

    # A user can leave promo input mode without accidentally redeeming a code.
    if low in ('назад', 'выйти', 'меню', '/назад', '/выйти', '/меню'):
        PROMO_WAITING.discard(uid)
        return await _original_text_handler(message, bot)

    # One-message form remains valid.
    if command in ('/промо', '/промокод', '/promo') and len(parts) >= 2:
        PROMO_WAITING.discard(uid)
        return await run.use_promo_extended(message, parts[1])
    if low.startswith('промо ') or low.startswith('промокод '):
        code = text.split(None, 1)[1].strip()
        if code:
            PROMO_WAITING.discard(uid)
            return await run.use_promo_extended(message, code)

    # Two-message form: first `промо`, then the code.
    if low in ('промо', 'промокод', '/промо', '/промокод', '/promo'):
        PROMO_WAITING.add(uid)
        return await message.answer('🎟 Введите промокод:')

    if uid in PROMO_WAITING and text and not text.startswith('/'):
        PROMO_WAITING.discard(uid)
        return await run.use_promo_extended(message, text)

    return await _original_text_handler(message, bot)


run.text_handler = patched_text_handler
print('[OAM] TWO-STEP PROMO INPUT: ON')
